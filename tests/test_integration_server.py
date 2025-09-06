"""Full integration tests for the Rust-backed server."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

import pytest

pytest.importorskip("forzium_engine")

from core.app import server  # noqa: E402
from forzium import ForziumApp  # noqa: E402
from forzium_engine import ForziumHttpServer  # noqa: E402
from tests.http_client import get, post  # noqa: E402


def start_core_server(port: int) -> ForziumHttpServer:
    """Start the default server on the given port."""
    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    return server


def test_health_endpoint() -> None:
    """Server responds to health checks."""
    srv = start_core_server(8200)
    try:
        resp = get("http://127.0.0.1:8200/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        srv.shutdown()


def test_compute_and_invalid() -> None:
    """Compute endpoint handles valid and invalid payloads."""
    srv = start_core_server(8201)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "add",
            "parameters": {"addend": 1},
        }
        resp = post("http://127.0.0.1:8201/compute", payload)
        assert resp.status_code == 200
        data = cast(dict[str, Any], resp.json())
        assert data["result"] == [[2, 3], [4, 5]]

        bad = {"data": [[1]], "operation": "divide", "parameters": {}}
        resp = post("http://127.0.0.1:8201/compute", bad)
        assert resp.status_code == 400
    finally:
        srv.shutdown()


def test_stream_endpoint() -> None:
    """Streaming results are returned as JSON lines."""
    srv = start_core_server(8202)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "multiply",
            "parameters": {"factor": 2},
        }
        resp = post("http://127.0.0.1:8202/stream", payload)
        assert resp.status_code == 200
        rows = [json.loads(line) for line in resp.text.strip().splitlines()]
        assert rows == [[2, 4], [6, 8]]
    finally:
        srv.shutdown()


def test_path_and_query_params() -> None:
    """Path and query parameters are passed to handlers."""
    srv = ForziumHttpServer()
    app = ForziumApp(srv)

    @app.get("/items/{item_id:int}")
    def read_item(item_id: int, q: str) -> dict:
        return {"item_id": item_id, "q": q}

    srv.serve("127.0.0.1:8203")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8203/items/5?q=foo")
        assert resp.status_code == 200
        assert resp.json() == {"item_id": 5, "q": "foo"}
    finally:
        srv.shutdown()


def test_parallel_health_requests() -> None:
    """Server handles concurrent health checks."""
    srv = start_core_server(8204)
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = [pool.submit(get, "http://127.0.0.1:8204/health") for _ in range(5)]
            responses = [f.result() for f in futs]
        for resp in responses:
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
    finally:
        srv.shutdown()
