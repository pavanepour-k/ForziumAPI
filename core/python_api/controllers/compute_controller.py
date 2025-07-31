"""Endpoint handlers for computation requests"""

from fastapi import APIRouter, HTTPException, Body
import asyncio

from ..models.request_models import ComputeRequest
from ..models.response_models import ComputeResponse
from ..services.orchestration_service import run_computation

router = APIRouter()


@router.post("/compute", response_model=ComputeResponse)
async def compute(request: dict = Body(...)) -> ComputeResponse:
    request = ComputeRequest(**request)
    """Execute a basic computation on the provided matrix"""
    try:
        result = await asyncio.to_thread(
            run_computation,
            request.data,
            request.operation,
            request.parameters,
        )
        return ComputeResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

__all__ = ["router"]