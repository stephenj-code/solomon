#!/usr/bin/env python3
"""
solomon-prometheus — MCP server exposing Prometheus query tools to Solomon.

Tools:
  prometheus_query        — instant PromQL query
  prometheus_query_range  — range PromQL query
  prometheus_get_alerts   — currently firing alerts
  prometheus_get_targets  — scrape target health

Connects to Prometheus via HTTP. URL configured by PROMETHEUS_URL env var
(default: http://prometheus.monitoring:9090).

Executed on-demand via `kubectl exec` by scripts/mcp-proxy.py — stdio transport.
"""

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("solomon-prometheus")

PROMETHEUS_URL = os.environ.get(
    "PROMETHEUS_URL", "http://prometheus-operated.observability:9090"
).rstrip("/")

_client = httpx.Client(base_url=PROMETHEUS_URL, timeout=30.0)


def _get(path: str, params: dict | None = None) -> dict:
    resp = _client.get(path, params=params or {})
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Prometheus error: {data.get('error', 'unknown')}")
    return data.get("data", {})


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def prometheus_query(query: str) -> str:
    """Execute an instant PromQL query. Returns current metric values."""
    try:
        data = _get("/api/v1/query", {"query": query})
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def prometheus_query_range(
    query: str,
    start: str,
    end: str,
    step: str = "60s",
) -> str:
    """
    Execute a range PromQL query.
    start/end: RFC3339 timestamp or Unix epoch (e.g. '2026-11-03T00:00:00Z' or '1762128000').
    step: duration string (e.g. '60s', '5m', '1h').
    """
    try:
        data = _get("/api/v1/query_range", {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        })
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def prometheus_get_alerts() -> str:
    """Get all currently firing Prometheus alerts with labels and annotations."""
    try:
        data = _get("/api/v1/alerts")
        alerts = data.get("alerts", [])
        firing = [a for a in alerts if a.get("state") == "firing"]
        return json.dumps(firing, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def prometheus_get_targets() -> str:
    """Get all active Prometheus scrape targets with health, last scrape, and errors."""
    try:
        data = _get("/api/v1/targets")
        active = data.get("activeTargets", [])
        result = [
            {
                "job": t.get("labels", {}).get("job"),
                "instance": t.get("labels", {}).get("instance"),
                "health": t.get("health"),
                "last_scrape": t.get("lastScrape"),
                "last_error": t.get("lastError") or None,
            }
            for t in active
        ]
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
