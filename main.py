from fastapi import FastAPI

from app.api.routers import health
from app.core.config import settings

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.app_debug)

app.include_router(health.router)
