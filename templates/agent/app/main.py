import logging

from fastapi import FastAPI

from app.config import settings
from app.routes import router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(router)

# Local dev: uvicorn app.main:app --reload   (run from project root)
