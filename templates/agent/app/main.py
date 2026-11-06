from fastapi import FastAPI
from app.config import settings
from app.routes import router

app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
