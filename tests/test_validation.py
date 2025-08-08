"""Validation performance comparisons."""

import pytest
from forzium import ComputeRequest
from interfaces.shared_types.compute_request import ComputeRequestModel


def test_rust_validation_matches_pydantic():
    payload = {
        "data": [[1, 2], [3, 4]],
        "operation": "add",
        "parameters": {},
    }
    py = ComputeRequestModel(**payload)
    rust = ComputeRequest(**payload)
    assert rust.dict() == py.model_dump()


def test_rust_validation_error():
    payload = {"data": [[1], [2, 3]], "operation": "add"}
    with pytest.raises(Exception):
        ComputeRequest(**payload)


def test_pydantic_validation_error():
    payload = {"data": [[1], [2, 3]], "operation": "add"}
    with pytest.raises(Exception):
        ComputeRequestModel(**payload)


def test_validation_performance():
    import time

    payload = {
        "data": [[1.0, 2.0], [3.0, 4.0]],
        "operation": "add",
    }
    start = time.perf_counter()
    ComputeRequest(**payload)
    duration = time.perf_counter() - start
    assert duration < 0.1
