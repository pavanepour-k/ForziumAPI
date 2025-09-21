# flake8: noqa
"""Forzium application routes defined via decorators."""
import json
from typing import Annotated, Any, Dict, Iterable, Tuple

from forzium_engine import ForziumHttpServer

from core.service.orchestration_service import run_computation, stream_computation
from forzium import ComputeRequest, Depends, ForziumApp
from forzium.responses import StreamingResponse
from forzium.security import api_key_query

server = ForziumHttpServer()
app = ForziumApp(server)
app.add_security_scheme(
    "ApiKey",
    {"type": "apiKey", "in": "query", "name": "api_key"},
)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check for the service"""
    return {"status": "ok"}


@app.post("/compute")
def compute(payload: dict[str, Any]) -> dict[str, Any] | Tuple[int, Dict[str, str]]:
    """Execute a basic computation on the provided matrix"""
    try:
        req = ComputeRequest(**payload)
    except Exception as exc:
        return 422, {"detail": str(exc)}
    return run_computation(req.data, req.operation, req.parameters)


@app.post("/stream")
def stream(payload: dict[str, Any]) -> StreamingResponse | Tuple[int, Dict[str, str]]:
    """Stream computation results row by row as JSON lines"""
    try:
        req = ComputeRequest(**payload)
    except Exception as exc:
        return 422, {"detail": str(exc)}

    def gen() -> Iterable[bytes]:
        for row in stream_computation(
            req.data,
            req.operation,
            req.parameters,
        ):
            yield json.dumps(row).encode() + b"\n"

    return StreamingResponse(gen(), media_type="application/json")


@app.get("/secure-data")
def secure_data(
    api_key: str = Depends(api_key_query),  # type: ignore[assignment]
) -> dict[str, str]:
    """Endpoint protected by API key passed via query parameter."""
    return {"message": "secured"}


__all__ = ["app", "server"]