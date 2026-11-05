#!/usr/bin/env python3
"""
solomon-kubernetes — MCP server exposing Kubernetes API tools to Solomon.

Tools:
  list_pods          — list pods (all namespaces or filtered)
  list_deployments   — list deployments (all namespaces or filtered)
  list_nodes         — list nodes with status, roles, version, IP
  get_pod_logs       — tail logs from a pod/container
  get_events         — cluster events, optionally filtered by namespace or type
  list_services      — list services
  list_namespaces    — list all namespaces
  get_deployment     — detailed info for a specific deployment
  restart_deployment — rollout restart (patches restartedAt annotation)
  list_ingress       — list Gateway API HTTPRoutes

Runs with in-cluster ServiceAccount (ClusterRole defined in deployment.yaml).
Executed on-demand via `kubectl exec` by scripts/mcp-proxy.py — stdio transport.
"""

import json
from datetime import datetime, timezone

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("solomon-kubernetes")

# Load in-cluster config; fall back to kubeconfig for local dev
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

_v1 = client.CoreV1Api()
_apps = client.AppsV1Api()
_custom = client.CustomObjectsApi()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _age(ts) -> str:
    if ts is None:
        return "unknown"
    delta = datetime.now(timezone.utc) - ts
    s = int(delta.total_seconds())
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def _pod_row(pod) -> dict:
    ready = sum(
        1 for cs in (pod.status.container_statuses or []) if cs.ready
    )
    total = len(pod.spec.containers)
    restarts = sum(
        cs.restart_count for cs in (pod.status.container_statuses or [])
    )
    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "node": pod.spec.node_name,
        "phase": pod.status.phase,
        "ready": f"{ready}/{total}",
        "restarts": restarts,
        "age": _age(pod.metadata.creation_timestamp),
    }


def _deploy_row(d) -> dict:
    return {
        "name": d.metadata.name,
        "namespace": d.metadata.namespace,
        "desired": d.spec.replicas,
        "ready": d.status.ready_replicas or 0,
        "available": d.status.available_replicas or 0,
        "age": _age(d.metadata.creation_timestamp),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_pods(namespace: str = "") -> str:
    """List pods. Pass namespace to filter; empty string = all namespaces."""
    try:
        items = (
            _v1.list_namespaced_pod(namespace).items
            if namespace
            else _v1.list_pod_for_all_namespaces().items
        )
        return json.dumps([_pod_row(p) for p in items], indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def list_deployments(namespace: str = "") -> str:
    """List deployments. Pass namespace to filter; empty string = all namespaces."""
    try:
        items = (
            _apps.list_namespaced_deployment(namespace).items
            if namespace
            else _apps.list_deployment_for_all_namespaces().items
        )
        return json.dumps([_deploy_row(d) for d in items], indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def list_nodes() -> str:
    """List cluster nodes with ready status, roles, kubelet version, and internal IP."""
    try:
        nodes = _v1.list_node().items
        result = []
        for n in nodes:
            conditions = {c.type: c.status for c in (n.status.conditions or [])}
            roles = [
                k.split("/", 1)[-1]
                for k in (n.metadata.labels or {})
                if k.startswith("node-role.kubernetes.io/")
            ]
            internal_ip = next(
                (a.address for a in (n.status.addresses or []) if a.type == "InternalIP"),
                None,
            )
            result.append({
                "name": n.metadata.name,
                "ready": conditions.get("Ready") == "True",
                "roles": roles or ["worker"],
                "version": n.status.node_info.kubelet_version,
                "internal_ip": internal_ip,
                "age": _age(n.metadata.creation_timestamp),
            })
        return json.dumps(result, indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def get_pod_logs(pod: str, namespace: str, container: str = "", tail: int = 100) -> str:
    """Get logs from a pod. Specify container name if the pod has multiple containers."""
    try:
        kwargs = {"tail_lines": tail}
        if container:
            kwargs["container"] = container
        return _v1.read_namespaced_pod_log(pod, namespace, **kwargs)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def get_events(namespace: str = "", event_type: str = "") -> str:
    """Get cluster events sorted by last seen. Filter by namespace and/or event_type (Normal|Warning)."""
    try:
        items = (
            _v1.list_namespaced_event(namespace).items
            if namespace
            else _v1.list_event_for_all_namespaces().items
        )
        result = []
        for e in items:
            if event_type and e.type != event_type:
                continue
            result.append({
                "namespace": e.metadata.namespace,
                "type": e.type,
                "reason": e.reason,
                "object": f"{e.involved_object.kind}/{e.involved_object.name}",
                "message": e.message,
                "count": e.count,
                "last_seen": str(e.last_timestamp),
            })
        result.sort(key=lambda x: str(x["last_seen"]), reverse=True)
        return json.dumps(result[:50], indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def list_services(namespace: str = "") -> str:
    """List services. Pass namespace to filter; empty string = all namespaces."""
    try:
        items = (
            _v1.list_namespaced_service(namespace).items
            if namespace
            else _v1.list_service_for_all_namespaces().items
        )
        result = []
        for s in items:
            result.append({
                "name": s.metadata.name,
                "namespace": s.metadata.namespace,
                "type": s.spec.type,
                "cluster_ip": s.spec.cluster_ip,
                "ports": [
                    f"{p.port}/{p.protocol}" for p in (s.spec.ports or [])
                ],
            })
        return json.dumps(result, indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def list_namespaces() -> str:
    """List all namespaces with phase and age."""
    try:
        items = _v1.list_namespace().items
        result = [
            {
                "name": ns.metadata.name,
                "status": ns.status.phase,
                "age": _age(ns.metadata.creation_timestamp),
            }
            for ns in items
        ]
        return json.dumps(result, indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def get_deployment(name: str, namespace: str) -> str:
    """Get detailed info for a specific deployment including conditions and image."""
    try:
        d = _apps.read_namespaced_deployment(name, namespace)
        containers = d.spec.template.spec.containers or []
        return json.dumps({
            "name": d.metadata.name,
            "namespace": d.metadata.namespace,
            "replicas": {
                "desired": d.spec.replicas,
                "ready": d.status.ready_replicas,
                "available": d.status.available_replicas,
                "updated": d.status.updated_replicas,
            },
            "images": {c.name: c.image for c in containers},
            "conditions": [
                {"type": c.type, "status": c.status, "message": c.message}
                for c in (d.status.conditions or [])
            ],
            "age": _age(d.metadata.creation_timestamp),
        }, indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def restart_deployment(name: str, namespace: str) -> str:
    """Trigger a rollout restart of a deployment (equivalent to kubectl rollout restart)."""
    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
                    }
                }
            }
        }
    }
    try:
        _apps.patch_namespaced_deployment(name, namespace, patch)
        return f"Rollout restart triggered: {namespace}/{name}"
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


@mcp.tool()
def list_ingress(namespace: str = "") -> str:
    """List Gateway API HTTPRoutes. Pass namespace to filter; empty string = all namespaces."""
    try:
        if namespace:
            resp = _custom.list_namespaced_custom_object(
                group="gateway.networking.k8s.io",
                version="v1",
                namespace=namespace,
                plural="httproutes",
            )
        else:
            resp = _custom.list_cluster_custom_object(
                group="gateway.networking.k8s.io",
                version="v1",
                plural="httproutes",
            )
        result = []
        for r in resp.get("items", []):
            result.append({
                "name": r["metadata"]["name"],
                "namespace": r["metadata"]["namespace"],
                "hostnames": r["spec"].get("hostnames", []),
                "backends": [
                    f"{b['name']}:{b['port']}"
                    for rule in r["spec"].get("rules", [])
                    for b in rule.get("backendRefs", [])
                ],
            })
        return json.dumps(result, indent=2)
    except ApiException as e:
        return f"Error: {e.reason} (HTTP {e.status})"


if __name__ == "__main__":
    mcp.run(transport="stdio")
