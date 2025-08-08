"""Tests for shared type helpers and protocols."""

import asyncio

from interfaces.protocols import AsyncComputeProtocol
from interfaces.shared_types import (
    ComputeRequestModel,
    Matrix,
)
from forzium_engine import multiply


def test_matrix_round_trip() -> None:
    """Matrix converts to Rust and back via multiply."""
    mat = Matrix([[1.0, 2.0]])
    out = Matrix.from_rust(multiply(mat.to_rust(), 2.0))
    assert out.rows == [[2.0, 4.0]]


class _DummyEngine:
    async def compute(self, req: ComputeRequestModel) -> list[list[float]]:
        return req.data

    async def close(self) -> None:
        return None


def test_protocol_runtime_check() -> None:
    """Dummy engine conforms to protocol."""
    engine = _DummyEngine()
    assert isinstance(engine, AsyncComputeProtocol)
    asyncio.run(
        engine.compute(
            ComputeRequestModel(data=[[1.0]], operation="add", parameters={})
        )
    )
