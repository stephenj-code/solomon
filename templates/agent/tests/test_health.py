"""
test_health.py — health endpoint test.

The graph is lazy-initialised (get_graph()) so importing app.main does not
trigger LangGraph or LiteLLM setup.  The health handler has no dependencies.
"""
from httpx import AsyncClient, ASGITransport

from app.main import app


async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
