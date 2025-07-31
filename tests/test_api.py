import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_compute_add():
    payload = {
        "data": [[1, 2], [3, 4]],
        "operation": "add",
        "parameters": {"addend": 1},
    }
    response = client.post("/compute", json=payload)
    assert response.status_code == 200
    assert response.json()["result"] == [[2, 3], [4, 5]]


def test_compute_multiply():
    payload = {
        "data": [[1, 2], [3, 4]],
        "operation": "multiply",
        "parameters": {"factor": 2},
    }
    response = client.post("/compute", json=payload)
    assert response.status_code == 200
    assert response.json()["result"] == [[2, 4], [6, 8]]


def test_compute_invalid_operation():
    payload = {"data": [[1]], "operation": "divide", "parameters": {}}
    response = client.post("/compute", json=payload)
    assert response.status_code == 400


def test_stream_invalid_operation():
    payload = {"data": [[1]], "operation": "divide", "parameters": {}}
    response = client.post("/stream", json=payload)
    assert response.status_code == 400


def test_stream_compute():
    payload = {
        "data": [[1, 2], [3, 4]],
        "operation": "multiply",
        "parameters": {"factor": 2},
    }
    response = client.post("/stream", json=payload)
    assert response.status_code == 200
    rows = [json.loads(line) for line in response.text.strip().splitlines()]
    assert rows == [[2, 4], [6, 8]]


def test_stream_value_error():
    payload = {
        "data": [[1, 2]],
        "operation": "multiply",
        "parameters": {"factor": "bad"},
    }
    response = client.post("/stream", json=payload)
    assert response.status_code == 400


def test_compute_matmul():
    payload = {
        "data": [[1, 2], [3, 4]],
        "operation": "matmul",
        "parameters": {"matrix_b": [[5, 6], [7, 8]]},
    }
    response = client.post("/compute", json=payload)
    assert response.status_code == 200
    assert response.json()["result"] == [[19, 22], [43, 50]]


def test_stream_matmul():
    payload = {
        "data": [[1, 2], [3, 4]],
        "operation": "matmul",
        "parameters": {"matrix_b": [[5, 6], [7, 8]]},
    }
    response = client.post("/stream", json=payload)
    assert response.status_code == 200
    rows = [json.loads(line) for line in response.text.strip().splitlines()]
    assert rows == [[19, 22], [43, 50]]
