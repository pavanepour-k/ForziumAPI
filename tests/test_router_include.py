"""Ensure routers can be included under a prefix."""

import time

import pytest

from forzium import ForziumApp
from forzium_engine import ForziumHttpServer
from tests.http_client import get

pytest.importorskip("forzium_engine")


def test_include_router_with_prefix() -> None:
    """Routes from a subrouter should be reachable via the prefix."""

    server = ForziumHttpServer()
    app = ForziumApp(server)
    sub = ForziumApp()

    @sub.get("/double/{x:int}")
    def double(x: int) -> dict:
        return {"result": x * 2}

    app.include_router(sub, prefix="/math")

    server.serve("127.0.0.1:8120")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8120/math/double/4")
        assert resp.status_code == 200
        assert resp.json() == {"result": 8}
    finally:
        server.shutdown()
