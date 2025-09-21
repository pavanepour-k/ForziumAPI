# ruff: noqa: E402
"""Property-based tests for GPU helpers."""

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import assume, given, strategies as st

from core.service.gpu import elementwise_add, elementwise_mul

pytestmark = pytest.mark.xfail(
    reason="GPU property operations not yet stable", strict=False
)

# Strategy generating square matrices of floats with size 1-4
matrix_strategy = st.integers(min_value=1, max_value=4).flatmap(
    lambda n: st.lists(
        st.lists(
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            min_size=n,
            max_size=n,
        ),
        min_size=n,
        max_size=n,
    )
)


@given(matrix_strategy, matrix_strategy)
def test_elementwise_add_commutative(a, b):
    """Addition should be commutative for matrices of same shape."""
    assume(len(a) == len(b) and all(len(x) == len(y) for x, y in zip(a, b)))
    assert elementwise_add(a, b) == elementwise_add(b, a)


@given(matrix_strategy)
def test_elementwise_add_identity(a):
    """Adding a zero matrix should return the original matrix."""
    zeros = [[0.0 for _ in row] for row in a]
    assert elementwise_add(a, zeros) == a


@given(matrix_strategy, matrix_strategy)
def test_elementwise_mul_commutative(a, b):
    """Elementwise multiplication should be commutative."""
    assume(len(a) == len(b) and all(len(x) == len(y) for x, y in zip(a, b)))
    assert elementwise_mul(a, b) == elementwise_mul(b, a)


@given(matrix_strategy)
def test_elementwise_mul_identity(a):
    """Multiplying by a ones matrix should return the original matrix."""
    ones = [[1.0 for _ in row] for row in a]
    assert elementwise_mul(a, ones) == a