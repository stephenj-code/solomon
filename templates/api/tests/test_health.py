"""
test_health.py — health and readiness endpoint tests.

get_db is overridden at module level so no real DB connection is ever attempted.
services.check_database is patched per-test to exercise the happy and failure paths.
"""
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport

from app.database import get_db
from app.main import app


async def _mock_db():
    yield object()  # placeholder — real session never used here


app.dependency_overrides[get_db] = _mock_db


async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_ready_ok():
    with patch("app.services.check_database", new_callable=AsyncMock, return_value="ok"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "ok"


async def test_ready_db_down():
    with patch(
        "app.services.check_database",
        new_callable=AsyncMock,
        side_effect=RuntimeError("database unreachable"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/ready")
    assert r.status_code == 503
