# ruff: noqa: E402
"""Tests for the gRPC computation interface."""

import json

import pytest

pytest.importorskip("google.protobuf")
from interfaces.grpc import forzium_pb2
from interfaces.grpc.server import ForziumServicer

def test_grpc_servicer() -> None:
    servicer = ForziumServicer()
    payload = {
        "data": [[1.0, 2.0]],
        "operation": "multiply",
        "parameters": {"factor": 2},
    }
    request = forzium_pb2.JsonPayload(payload=json.dumps(payload).encode())
    response = servicer.Compute(request, None)
    data = json.loads(response.payload.decode())
    assert data["result"] == [[2.0, 4.0]]


def test_grpc_streaming() -> None:
    servicer = ForziumServicer()
    payload = {
        "data": [[1.0, 2.0]],
        "operation": "multiply",
        "parameters": {"factor": 2},
    }
    request = forzium_pb2.JsonPayload(payload=json.dumps(payload).encode())
    responses = list(servicer.StreamCompute(request, None))
    rows = [json.loads(r.payload.decode()) for r in responses]
    assert rows == [[2.0, 4.0]]
