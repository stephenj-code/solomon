from fastapi import FastAPI
from app.config import settings
from app.routes import router

app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(router)

# Local dev: uvicorn app.main:app --reload   (run from project root)
# Production: uvicorn handles startup (see Dockerfile CMD)
