"""Simple health-check endpoints"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check() -> dict:
    """Simple liveness check for the service"""
    return {"status": "ok"}

__all__ = ["router"]