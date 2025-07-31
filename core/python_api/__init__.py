"""FastAPI application setup and configuration"""

from fastapi import FastAPI
from .controllers import api_router
from .models.config_models import Settings

settings = Settings()

app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(api_router)

__all__ = ["app", "settings"]