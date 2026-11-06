"""
test_steps.py — unit tests for steps.py.

All external calls live in services.py, so each test patches only the relevant
service function.  No DB, no HTTP, no LiteLLM required.
"""
from unittest.mock import AsyncMock, patch

from app.models import Item, Result
from app.steps import fetch_input, process, write_output


async def test_fetch_input_returns_list():
    with patch("app.services.list_items", new_callable=AsyncMock, return_value=[]):
        result = await fetch_input()
    assert result == []


async def test_process_empty_list():
    result = await process([])
    assert result == []


async def test_process_calls_service_per_item():
    items = [Item(id="1", name="a"), Item(id="2", name="b")]
    stub = Result(item_id="1", value="x")
    with patch("app.services.process_item", new_callable=AsyncMock, return_value=stub) as mock_svc:
        results = await process(items)
    assert mock_svc.call_count == 2
    assert len(results) == 2


async def test_write_output_calls_upsert_per_result():
    results = [Result(item_id="1", value="x"), Result(item_id="2", value="y")]
    with patch("app.services.upsert_result", new_callable=AsyncMock) as mock_upsert:
        await write_output(results)
    assert mock_upsert.call_count == 2
