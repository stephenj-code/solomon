"""
services.py — capabilities.

Business logic and external calls live here. Handlers call services.
Services never import from handlers or routes.

Rules:
  - One async function per distinct operation
  - Raise plain Python exceptions (ValueError, RuntimeError) — handlers convert to HTTPException
  - All database queries go here, not in handlers
  - All calls to LiteLLM, external APIs go here

Idempotency pattern for writes:
  Use INSERT ... ON CONFLICT DO UPDATE (upsert) so calling the same
  operation twice produces the same result, never a duplicate.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def check_database(db: AsyncSession) -> str:
    """Returns 'ok' if the database is reachable, raises RuntimeError if not."""
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.error("database health check failed: %s", exc, exc_info=True)
        raise RuntimeError("database unreachable") from exc


# --- Add your domain service functions below ---
# Example:
#
# async def create_item(db: AsyncSession, name: str, value: float) -> dict:
#     result = await db.execute(
#         text("""
#         INSERT INTO items (id, name, value)
#         VALUES (gen_random_uuid(), :name, :value)
#         ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value
#         RETURNING id, name, value, created_at
#         """),
#         {"name": name, "value": value},
#     )
#     return result.mappings().one()
