"""Tests for Rust-Python FFI bindings."""

import pytest

from forzium_engine import echo_list, sum_list


def test_echo_list_roundtrip() -> None:
    """Sequences convert to Rust and back unchanged."""
    assert echo_list((1, 2, 3)) == [1, 2, 3]


def test_sum_list_and_error() -> None:
    """Sum succeeds for values and errors on empty input."""
    assert sum_list([1, 2, 3]) == 6
    with pytest.raises(ValueError):
        sum_list([])
