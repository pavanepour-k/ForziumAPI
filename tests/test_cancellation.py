"""Tests for cancellation tokens and error propagation."""

import pytest

from core.service import orchestration_service as svc
from interfaces.shared_types.cancellation import CancellationToken


def test_run_computation_cancellation() -> None:
    token = CancellationToken()
    token.cancel()
    with pytest.raises(RuntimeError):
        svc.run_computation([[1.0]], "multiply", {"factor": 2}, token)


def test_error_propagation() -> None:
    token = CancellationToken()
    with pytest.raises(ValueError):
        svc.run_computation([[1.0]], "unknown", {}, token)
