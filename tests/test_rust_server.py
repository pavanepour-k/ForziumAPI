import httpx
import time
from forzium_engine import ForziumHttpServer


def test_rust_server_health():
    server = ForziumHttpServer()
    server.serve("127.0.0.1:8090")
    # Wait briefly for server to start
    time.sleep(0.2)
    try:
        resp = httpx.get("http://127.0.0.1:8090/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        server.shutdown()


def test_rust_server_concurrent():
    server = ForziumHttpServer()
    server.serve("127.0.0.1:8091")
    time.sleep(0.2)
    try:
        with httpx.Client() as client:
            responses = [client.get("http://127.0.0.1:8091/health") for _ in range(5)]
        for resp in responses:
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
    finally:
        server.shutdown()