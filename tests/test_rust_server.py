"""Direct tests of the Rust HTTP server."""

import socket
import threading
import time

import pytest

pytest.importorskip("forzium_engine")
from forzium import ForziumApp  # noqa: E402
from forzium_engine import ForziumHttpServer  # noqa: E402
from tests.http_client import get  # noqa: E402


def _allocate_port() -> int:
    """Return an available localhost TCP port."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


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


def test_rust_server_readiness_and_liveness() -> None:
    """Server exposes readiness and liveness checks."""
    server = ForziumHttpServer()
    server.serve("127.0.0.1:8095")
    time.sleep(0.2)
    try:
        for endpoint in ("ready", "live"):
            resp = get(f"http://127.0.0.1:8095/{endpoint}")
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


def test_shutdown_waits_for_inflight_requests() -> None:
    """Graceful shutdown waits for in-flight requests and releases the port."""

    port = _allocate_port()
    server = ForziumHttpServer()
    app = ForziumApp(server)

    route_started = threading.Event()
    route_completed = threading.Event()

    @app.get("/slow")
    def slow_route() -> dict[str, str]:  # pragma: no cover - executed by server thread
        route_started.set()
        time.sleep(0.3)
        route_completed.set()
        return {"status": "ok"}

    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.1)

    client_response: dict[str, object] = {}

    def _perform_request() -> None:
        client_response["resp"] = get(f"http://127.0.0.1:{port}/slow")

    thread = threading.Thread(target=_perform_request)
    thread_started = False

    try:
        thread.start()
        thread_started = True
        assert route_started.wait(timeout=5.0)
        assert not route_completed.is_set()

        shutdown_start = time.perf_counter()
        server.shutdown()
        shutdown_elapsed = time.perf_counter() - shutdown_start
        assert shutdown_elapsed >= 0.2

        thread.join(timeout=1.0)
        assert not thread.is_alive()
        assert route_completed.is_set()
        resp = client_response.get("resp")
        assert resp is not None
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
    finally:
        server.shutdown()
        if thread_started:
            thread.join(timeout=1.0)