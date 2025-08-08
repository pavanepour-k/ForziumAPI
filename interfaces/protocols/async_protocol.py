"""Async protocol definitions for services"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from interfaces.shared_types import ComputeRequestModel


@runtime_checkable
class AsyncComputeProtocol(Protocol):
    """Behaviour contract for async compute services."""

    async def compute(self, req: ComputeRequestModel) -> list[list[float]]:
        """Execute a computation asynchronously."""

    async def close(self) -> None:
        """Shut down any held resources."""
