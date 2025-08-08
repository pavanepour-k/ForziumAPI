"""Integration tests hitting the Rust server directly."""

import json
import time

import pytest

pytest.importorskip("forzium_engine")
from forzium_engine import ForziumHttpServer  # noqa: E402

from core import server  # noqa: E402
from tests.http_client import post  # noqa: E402


def start_server(port: int) -> ForziumHttpServer:
    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    return server


def test_compute_via_rust_server():
    server = start_server(8092)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "add",
            "parameters": {"addend": 1},
        }
        resp = post("http://127.0.0.1:8092/compute", payload)
        assert resp.status_code == 200
        assert resp.json()["result"] == [[2, 3], [4, 5]]
    finally:
        server.shutdown()


def test_compute_invalid_operation_via_rust_server():
    server = start_server(8094)
    try:
        payload = {"data": [[1]], "operation": "divide", "parameters": {}}
        resp = post("http://127.0.0.1:8094/compute", payload)
        assert resp.status_code == 400
    finally:
        server.shutdown()


def test_stream_via_rust_server():
    server = start_server(8093)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "multiply",
            "parameters": {"factor": 2},
        }
        resp = post("http://127.0.0.1:8093/stream", payload)
        assert resp.status_code == 200
        rows = [json.loads(line) for line in resp.text.strip().splitlines()]
        assert rows == [[2, 4], [6, 8]]
    finally:
        server.shutdown()


def test_stream_invalid_operation_via_rust_server():
    server = start_server(8095)
    try:
        payload = {"data": [[1]], "operation": "divide", "parameters": {}}
        resp = post("http://127.0.0.1:8095/stream", payload)
        assert resp.status_code == 400
    finally:
        server.shutdown()
