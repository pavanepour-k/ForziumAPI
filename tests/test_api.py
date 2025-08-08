"""Integration tests for the Python-facing API routes."""

import json
import time
from typing import Any, cast

import pytest

pytest.importorskip("forzium_engine")
from forzium_engine import ForziumHttpServer  # noqa: E402
from core import server  # noqa: E402
from tests.http_client import get, post  # noqa: E402


def start_server(port: int) -> ForziumHttpServer:
    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    return server


def test_health():
    server = start_server(8100)
    try:
        resp = get("http://127.0.0.1:8100/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        server.shutdown()


def test_compute_add():
    server = start_server(8101)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "add",
            "parameters": {"addend": 1},
        }
        resp = post("http://127.0.0.1:8101/compute", payload)
        assert resp.status_code == 200
        data = cast(dict[str, Any], resp.json())
        assert data["result"] == [[2, 3], [4, 5]]
    finally:
        server.shutdown()


def test_compute_multiply():
    server = start_server(8102)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "multiply",
            "parameters": {"factor": 2},
        }
        resp = post("http://127.0.0.1:8102/compute", payload)
        assert resp.status_code == 200
        data = cast(dict[str, Any], resp.json())
        assert data["result"] == [[2, 4], [6, 8]]
    finally:
        server.shutdown()


def test_compute_invalid_operation():
    server = start_server(8103)
    try:
        payload = {"data": [[1]], "operation": "divide", "parameters": {}}
        resp = post("http://127.0.0.1:8103/compute", payload)
        assert resp.status_code == 400
    finally:
        server.shutdown()


def test_compute_invalid_data() -> None:
    server = start_server(8109)
    try:
        payload = {
            "data": [[1], [2, 3]],
            "operation": "add",
            "parameters": {},
        }
        resp = post("http://127.0.0.1:8109/compute", payload)
        assert resp.status_code == 422
        data = cast(dict[str, Any], resp.json())
        assert data["detail"]
    finally:
        server.shutdown()


def test_stream_invalid_operation():
    server = start_server(8104)
    try:
        payload = {"data": [[1]], "operation": "divide", "parameters": {}}
        resp = post("http://127.0.0.1:8104/stream", payload)
        assert resp.status_code == 400
    finally:
        server.shutdown()


def test_stream_compute():
    server = start_server(8105)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "multiply",
            "parameters": {"factor": 2},
        }
        resp = post("http://127.0.0.1:8105/stream", payload)
        assert resp.status_code == 200
        rows = [json.loads(line) for line in resp.text.strip().splitlines()]
        assert rows == [[2, 4], [6, 8]]
    finally:
        server.shutdown()


def test_stream_value_error():
    server = start_server(8106)
    try:
        payload = {
            "data": [[1, 2]],
            "operation": "multiply",
            "parameters": {"factor": "bad"},
        }
        resp = post("http://127.0.0.1:8106/stream", payload)
        assert resp.status_code == 400
    finally:
        server.shutdown()


def test_compute_matmul():
    server = start_server(8107)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "matmul",
            "parameters": {"matrix_b": [[5, 6], [7, 8]]},
        }
        resp = post("http://127.0.0.1:8107/compute", payload)
        assert resp.status_code == 200
        data = cast(dict[str, Any], resp.json())
        assert data["result"] == [[19, 22], [43, 50]]
    finally:
        server.shutdown()


def test_stream_matmul():
    server = start_server(8108)
    try:
        payload = {
            "data": [[1, 2], [3, 4]],
            "operation": "matmul",
            "parameters": {"matrix_b": [[5, 6], [7, 8]]},
        }
        resp = post("http://127.0.0.1:8108/stream", payload)
        assert resp.status_code == 200
        rows = [json.loads(line) for line in resp.text.strip().splitlines()]
        assert rows == [[19, 22], [43, 50]]
    finally:
        server.shutdown()
