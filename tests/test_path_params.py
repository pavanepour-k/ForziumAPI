"""Tests for dynamic path parameter handling in the Rust server."""

import time

import pytest

pytest.importorskip("forzium_engine")
from forzium import ForziumApp  # noqa: E402
from forzium_engine import ForziumHttpServer  # noqa: E402
from tests.http_client import get  # noqa: E402


def test_path_parameters():
    """Server should extract and convert path parameters."""

    server = ForziumHttpServer()
    app = ForziumApp(server)

    @app.get("/add/{x:int}/{y:int}")
    def add(x: int, y: int) -> dict:
        return {"result": x + y}

    server.serve("127.0.0.1:8110")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8110/add/3/5")
        assert resp.status_code == 200
        assert resp.json() == {"result": 8}

        resp = get("http://127.0.0.1:8110/add/three/5")
        assert resp.status_code == 400
    finally:
        server.shutdown()
