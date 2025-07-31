from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
import json
from typing import AsyncIterator

from ..models.request_models import ComputeRequest
from ..services.orchestration_service import stream_computation

router = APIRouter()

@router.get("/stream")
def stream_placeholder() -> dict:
    """Placeholder status endpoint"""
    return {"message": "streaming available"}

@router.post("/stream", response_class=StreamingResponse)
async def stream_compute(request: dict = Body(...)) -> StreamingResponse:
    request = ComputeRequest(**request)
    """Stream computation results row by row as JSON lines"""

    if request.operation not in {"add", "multiply", "matmul"}:
        raise HTTPException(status_code=400, detail="Unsupported operation")

    # Pre-validate numeric parameters to surface errors before streaming
    try:
        if request.operation == "multiply":
            float(request.parameters.get("factor", 1))
        elif request.operation == "add":
            float(request.parameters.get("addend", 0))
        else:
            if not isinstance(request.parameters.get("matrix_b"), list):
                raise ValueError("matrix_b parameter required")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
        
    async def row_generator() -> AsyncIterator[str]:
        try:
            for row in stream_computation(
                request.data,
                request.operation,
                request.parameters,
            ):
                yield json.dumps(row) + "\n"
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return StreamingResponse(row_generator(), media_type="application/json")

__all__ = ["router"]