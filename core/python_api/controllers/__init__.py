"""Router composition for all API endpoints"""

from fastapi import APIRouter

from .health_controller import router as health_router
from .compute_controller import router as compute_router
from .stream_controller import router as stream_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(compute_router)
api_router.include_router(stream_router)

__all__ = ["api_router"]