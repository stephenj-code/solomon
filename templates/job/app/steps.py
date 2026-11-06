"""
steps.py — logic.

One async function per step. Steps call services to do the actual work.
Steps never contain direct DB queries or HTTP calls — that belongs in services.py.
"""
from app import services
from app.models import Item, Result


async def fetch_input() -> list[Item]:
    """Fetch the data this job will process."""
    return await services.list_items()


async def process(items: list[Item]) -> list[Result]:
    """Transform each item into a result."""
    results = []
    for item in items:
        result = await services.process_item(item)
        results.append(result)
    return results


async def write_output(results: list[Result]) -> None:
    """Persist the results. Idempotent — safe to retry."""
    for result in results:
        await services.upsert_result(result)
