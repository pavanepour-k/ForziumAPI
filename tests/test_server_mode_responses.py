import socket
import time

import pytest

pytest.importorskip("forzium_engine")

from forzium import ForziumApp
from forzium.http import Response
from forzium.responses import JSONResponse
from forzium_engine import ForziumHttpServer
from tests.http_client import get


def _allocate_port() -> int:
    """Return an available TCP port bound to localhost."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_server_mode_preserves_success_response() -> None:
    """Tuple/Response outputs propagate status, headers, and body."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)

    @app.get("/tuple")
    def tuple_route() -> JSONResponse:
        return JSONResponse(
            {"message": "created"},
            status_code=202,
            headers={"x-powered-by": "rust-core"},
        )

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    try:
        resp = get(f"http://127.0.0.1:{port}/tuple")
        assert resp.status_code == 202
        assert resp.json() == {"message": "created"}
        assert resp.headers["x-powered-by"] == "rust-core"
        assert resp.headers["content-type"] == "application/json"
    finally:
        server.shutdown()


def test_server_mode_preserves_error_payload() -> None:
    """Error responses from handlers maintain JSON schema and headers."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)

    @app.get("/fail")
    def fail_route() -> None:
        raise ValueError("invalid state")

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    try:
        resp = get(f"http://127.0.0.1:{port}/fail")
        assert resp.status_code == 400
        assert resp.json() == {"detail": "invalid state"}
        assert resp.headers["content-type"] == "application/json"
    finally:
        server.shutdown()


def test_server_mode_path_param_validation_schema() -> None:
    """Invalid path parameters return FastAPI-compatible 422 payload."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)

    @app.get("/items/{item_id:int}")
    def read_item(item_id: int) -> dict[str, int]:  # pragma: no cover - executed via server
        return {"item_id": item_id}

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    try:
        resp = get(f"http://127.0.0.1:{port}/items/not-a-number")
        assert resp.status_code == 422
        assert resp.json() == {
            "detail": [
                {
                    "loc": ["path", "item_id"],
                    "msg": "value is not a valid integer",
                    "type": "type_error.integer",
                }
            ]
        }
        assert resp.headers["content-type"] == "application/json"
    finally:
        server.shutdown()


def test_server_mode_internal_error_schema() -> None:
    """Unhandled exceptions map to standardized 500 responses."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)

    @app.get("/boom")
    def boom() -> None:  # pragma: no cover - executed via server
        raise RuntimeError("boom")

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    try:
        resp = get(f"http://127.0.0.1:{port}/boom")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal Server Error"}
        assert resp.headers["content-type"] == "application/json"
    finally:
        server.shutdown()


def test_server_mode_preserves_binary_body() -> None:
    """Binary response bodies are delivered byte-for-byte."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)

    payload = bytes(range(256))

    @app.get("/binary")
    def binary_route() -> Response:  # pragma: no cover - executed via server
        return Response(
            payload,
            media_type="application/octet-stream",
            headers={"X-Mode": "bin"},
        )

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    try:
        resp = get(f"http://127.0.0.1:{port}/binary")
        assert resp.status_code == 200
        assert resp.content == payload
        assert resp.headers["content-type"] == "application/octet-stream"
        assert resp.headers["x-mode"] == "bin"
    finally:
        server.shutdown()