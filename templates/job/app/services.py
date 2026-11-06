"""
services.py — capabilities.

External calls: DB queries, HTTP requests, LiteLLM.
Steps call services — services never import from steps or job.

Rules:
  - One async function per distinct operation
  - Raise plain Python exceptions (ValueError, RuntimeError)
  - Use httpx.AsyncClient for HTTP — not requests (sync)
  - Use INSERT ... ON CONFLICT DO UPDATE for all writes (idempotent)
  - Never log secret values, tokens, or connection strings
"""
import logging

import httpx

from app.models import Item, Result

logger = logging.getLogger(__name__)


async def fetch_external(url: str) -> dict:
    """Example: fetch JSON from an external URL."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP %s fetching %s", exc.response.status_code, url)
        raise RuntimeError(f"upstream returned {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.error("request failed for %s: %s", url, exc, exc_info=True)
        raise RuntimeError("upstream request failed") from exc


# --- Replace these stubs with real operations ---

async def list_items() -> list[Item]:
    """Fetch the items to process. Replace with real DB query or API call."""
    return []


async def process_item(item: Item) -> Result:
    """Process one item. Replace with real logic."""
    return Result(item_id=item.id, value=f"processed:{item.name}")


async def upsert_result(result: Result) -> None:
    """Write one result. Use upsert so retries are safe.

    Example SQL pattern:
        INSERT INTO results (id, item_id, value)
        VALUES (gen_random_uuid(), $1, $2)
        ON CONFLICT (item_id) DO UPDATE SET value = EXCLUDED.value
    """
    pass
