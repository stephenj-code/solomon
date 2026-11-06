import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

from app import handlers
from app.agent.graph import build_graph
from app.config import settings
from app.routes import router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db_url = settings.database_url.get_secret_value()
    if db_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # AsyncPostgresSaver uses psycopg3 — strip the SQLAlchemy asyncpg dialect prefix
        conn_str = db_url.replace("postgresql+asyncpg://", "postgresql://")
        async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
            await checkpointer.setup()  # creates LangGraph checkpoint tables if absent
            handlers.set_graph(build_graph(checkpointer=checkpointer))
            yield
    else:
        # No DATABASE_URL — in-memory checkpointer (local dev / CI tests)
        # Conversations are not durable across restarts in this mode.
        handlers.set_graph(build_graph(checkpointer=MemorySaver()))
        yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
app.include_router(router)

# Local dev: uvicorn app.main:app --reload   (run from project root)
