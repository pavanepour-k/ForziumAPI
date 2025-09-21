"""Tests for data transformation routines exposed via PyO3."""

import pytest

from forzium_engine import normalize, reshape, scale


def test_normalize() -> None:
    assert normalize([1.0, 2.0, 3.0]) == [0.0, 0.5, 1.0]


def test_scale() -> None:
    assert scale([1.0, 2.0], 3.0) == [3.0, 6.0]


def test_reshape() -> None:
    vec = [1.0, 2.0, 3.0, 4.0]
    assert reshape(vec, 2, 2) == [[1.0, 2.0], [3.0, 4.0]]


def test_normalize_constant_error() -> None:
    with pytest.raises(ValueError):
        normalize([1.0, 1.0])
