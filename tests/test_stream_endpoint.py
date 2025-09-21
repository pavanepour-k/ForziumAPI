import json

from core.app import app
from forzium.testclient import TestClient


def test_stream_endpoint_returns_chunks() -> None:
    client = TestClient(app)
    payload = {
        "data": [[1, 2], [3, 4]],
        "operation": "multiply",
        "parameters": {"factor": 2},
    }
    resp = client.post("/stream", json_body=payload)
    assert resp.status_code == 200
    assert resp.chunks is not None
    rows = [json.loads(line) for line in resp.chunks]
    assert rows == [[2, 4], [6, 8]]


def test_stream_endpoint_large_dataset() -> None:
    client = TestClient(app)
    data = [[i] for i in range(10000)]
    payload = {
        "data": data,
        "operation": "add",
        "parameters": {"addend": 1},
    }
    resp = client.post("/stream", json_body=payload)
    assert resp.status_code == 200
    assert resp.chunks is not None
    assert len(resp.chunks) == 10000