"""Forzium application routes defined via decorators."""

import json
from typing import Any, Dict, Tuple

from forzium import ComputeRequest, ForziumApp
from forzium_engine import ForziumHttpServer
from core.service.orchestration_service import (
    run_computation,
    stream_computation,
)


server = ForziumHttpServer()
app = ForziumApp(server)


@app.get("/health")
def health() -> dict:
    """Simple liveness check for the service"""
    return {"status": "ok"}


@app.post("/compute")
def compute(payload: dict) -> dict[str, Any] | Tuple[int, Dict[str, str]]:
    """Execute a basic computation on the provided matrix"""
    try:
        req = ComputeRequest(**payload)
    except Exception as exc:
        return 422, {"detail": str(exc)}
    return run_computation(req.data, req.operation, req.parameters)


@app.post("/stream")
def stream(payload: dict) -> str | Tuple[int, Dict[str, str]]:
    """Stream computation results row by row as JSON lines"""
    try:
        req = ComputeRequest(**payload)
    except Exception as exc:
        return 422, {"detail": str(exc)}
    lines = (
        json.dumps(row)
        for row in stream_computation(
            req.data,
            req.operation,
            req.parameters,
        )
    )  # Reason: avoid storing all rows before joining
    return "\n".join(lines)


__all__ = ["app", "server"]
