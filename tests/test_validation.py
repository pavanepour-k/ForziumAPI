
from forzium import ComputeRequest
import pytest


class PyComputeRequest:
    """Lightweight validator mimicking previous Pydantic model."""

    def __init__(self, **data: object) -> None:
        matrix = data.get("data")
        if not matrix or any(len(row) != len(matrix[0]) for row in matrix):
            raise ValueError("Data must be a non-empty rectangular matrix")
        self.data = matrix
        self.operation = data.get("operation")
        self.parameters = data.get("parameters", {})

    def model_dump(self) -> dict:
        return {
            "data": self.data,
            "operation": self.operation,
            "parameters": self.parameters,
        }


def test_rust_validation_matches_pydantic():
    payload = {"data": [[1, 2], [3, 4]], "operation": "add", "parameters": {}}
    py = PyComputeRequest(**payload)
    rust = ComputeRequest(**payload)
    assert rust.dict() == py.model_dump()


def test_rust_validation_error():
    payload = {"data": [[1], [2, 3]], "operation": "add"}
    with pytest.raises(Exception):
        ComputeRequest(**payload)


def test_validation_performance():
    payload = {"data": [[1.0, 2.0], [3.0, 4.0]], "operation": "add"}
    import time

    start = time.perf_counter()
    for _ in range(1000):
        ComputeRequest(**payload)
    rust_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(1000):
        PyComputeRequest(**payload)
    py_time = time.perf_counter() - start

    # Allow some leeway as the pure Python version is minimal
    assert rust_time <= py_time * 3