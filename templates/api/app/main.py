from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.routes import router

app = FastAPI(title=settings.app_name, version=settings.version)

# Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)

app.include_router(router)


# Local dev: uvicorn app.main:app --reload   (run from project root)
# Production: gunicorn handles startup (see Dockerfile CMD)
