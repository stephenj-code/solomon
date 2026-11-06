"""
handlers.py — logic.

One async function per endpoint. Handlers:
  - Receive validated request data (FastAPI injects it)
  - Call services to do the actual work
  - Return a typed model from models.py
  - Convert service exceptions to HTTPException

Handlers contain no business logic — that belongs in services.py.
"""
import logging

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import HealthResponse, ReadyResponse
from app import services

logger = logging.getLogger(__name__)


async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.version)


async def ready(db: AsyncSession = Depends(get_db)) -> ReadyResponse:
    try:
        db_status = await services.check_database(db)
    except RuntimeError as exc:
        logger.warning("readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReadyResponse(status="ok", database=db_status)


# --- Add your domain handlers below ---
# Example:
#
# async def create_item(
#     body: ItemCreate,
#     db: AsyncSession = Depends(get_db),
# ) -> ItemResponse:
#     try:
#         row = await services.create_item(db, body.name, body.value)
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     return ItemResponse(**row)
