"""Data types used across language boundaries."""

from .cancellation import CancellationToken
from .collections import Matrix
from .primitives import Float64

__all__ = ["Float64", "Matrix", "ComputeRequestModel", "CancellationToken"]


def __getattr__(name: str):  # pragma: no cover - simple proxy
    if name == "ComputeRequestModel":
        from .compute_request import ComputeRequestModel  # local import

        return ComputeRequestModel
    raise AttributeError(name)
