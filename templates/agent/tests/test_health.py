"""
test_health.py — health endpoint test.

main.py lifespan checks DATABASE_URL at startup. When empty (CI / local dev),
it falls back to MemorySaver so no real Postgres connection is attempted.
The health handler does not use the graph, so this test is always fast.
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
