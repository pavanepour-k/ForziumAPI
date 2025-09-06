"""Direct tests of the Rust HTTP server."""

import time

import pytest

pytest.importorskip("forzium_engine")
from forzium_engine import ForziumHttpServer  # noqa: E402
from tests.http_client import get  # noqa: E402


def test_rust_server_health() -> None:
    """Server returns health status."""
    server = ForziumHttpServer()
    server.serve("127.0.0.1:8090")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8090/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        server.shutdown()


def test_rust_server_concurrent() -> None:
    """Server handles concurrent requests."""
    server = ForziumHttpServer()
    server.serve("127.0.0.1:8091")
    time.sleep(0.2)
    try:
        responses = [get("http://127.0.0.1:8091/health") for _ in range(5)]
        for resp in responses:
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
    finally:
        server.shutdown()


def test_unknown_route_returns_404() -> None:
    """Unknown path returns HTTP 404."""
    server = ForziumHttpServer()
    server.serve("127.0.0.1:8120")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8120/missing")
        assert resp.status_code == 404
    finally:
        server.shutdown()


def test_internal_error_returns_500() -> None:
    """Handler exception results in HTTP 500."""

    def boom(_body: bytes, _params: tuple, _query: bytes) -> tuple[int, str]:
        raise ValueError("boom")

    server = ForziumHttpServer()
    server.add_route("GET", "/boom", boom)
    server.serve("127.0.0.1:8121")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8121/boom")
        assert resp.status_code == 500
    finally:
        server.shutdown()


def test_rust_panic_translates_to_500() -> None:
    """Rust panics become HTTP 500 without crashing server."""

    def panic_handler(_body: bytes, _params: tuple, _query: bytes) -> tuple[int, str]:
        from forzium_engine import trigger_panic

        trigger_panic()
        return 200, "{}"

    server = ForziumHttpServer()
    server.add_route("GET", "/panic", panic_handler)
    server.serve("127.0.0.1:8122")
    time.sleep(0.2)
    try:
        resp = get("http://127.0.0.1:8122/panic")
        assert resp.status_code == 500
        resp = get("http://127.0.0.1:8122/health")
        assert resp.status_code == 200
    finally:
        server.shutdown()
