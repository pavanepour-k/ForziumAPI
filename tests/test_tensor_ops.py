"""Tests for tensor operations exposed via PyO3."""

import pytest

from forzium_engine import (
    conv2d,
    elementwise_add,
    matmul,
    max_pool2d,
    simd_elementwise_add,
    transpose,
)


def test_transpose() -> None:
    assert transpose([[1.0, 2.0], [3.0, 4.0]]) == [[1.0, 3.0], [2.0, 4.0]]


def test_elementwise_add() -> None:
    a = [[1.0, 2.0], [3.0, 4.0]]
    b = [[5.0, 6.0], [7.0, 8.0]]
    assert elementwise_add(a, b) == [[6.0, 8.0], [10.0, 12.0]]


def test_simd_elementwise_add() -> None:
    a = [[1.0, 2.0], [3.0, 4.0]]
    b = [[5.0, 6.0], [7.0, 8.0]]
    assert simd_elementwise_add(a, b) == [[6.0, 8.0], [10.0, 12.0]]


def test_conv2d_and_pool() -> None:
    mat = [[1.0, 2.0], [3.0, 4.0]]
    kernel = [[1.0]]
    assert conv2d(mat, kernel) == mat
    assert max_pool2d(mat, 2) == [[4.0]]


def test_matmul_shape_mismatch() -> None:
    a = [[1.0, 2.0]]
    b = [[1.0], [2.0], [3.0]]
    with pytest.raises(ValueError):
        matmul(a, b)
