"""Tests query parameter parsing in the Rust server."""

import time

from forzium import ForziumApp
from forzium_engine import ForziumHttpServer
from tests.http_client import get


def test_query_parameters() -> None:
    """Query parameters are extracted and passed to handlers."""
    server = ForziumHttpServer()
    app = ForziumApp(server)

    @app.get("/items/{item_id:int}")
    def read_item(item_id: int, q: str) -> dict:
        return {"item_id": item_id, "q": q}

    server.serve("127.0.0.1:8111")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8111/items/5?q=foo")
        assert resp.status_code == 200
        assert resp.json() == {"item_id": 5, "q": "foo"}
    finally:
        server.shutdown()
