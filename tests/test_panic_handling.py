"""Ensure Rust panics surface as Python exceptions."""

import pytest
from forzium_engine import trigger_panic


def test_rust_panic_converts_to_exception() -> None:
    """Triggering a Rust panic raises an exception."""
    with pytest.raises(BaseException):
        trigger_panic()
