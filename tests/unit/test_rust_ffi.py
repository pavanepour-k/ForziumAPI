"""
Unit tests for Rust FFI functions.

Tests all public Rust functions exposed through PyO3 bindings,
including tensor operations, data transforms, and utility functions.
"""

import math
import sys
from typing import List

import pytest

# Skip all tests in this module if Rust engine is not available
try:
    import forzium_engine
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="Rust engine not available")


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestTensorOperations:
    """Test basic tensor operations (multiply, add, transpose)."""

    def test_multiply_basic(self, small_matrix):
        """Test matrix scalar multiplication with small matrix."""
        result = forzium_engine.multiply(small_matrix, 2.0)
        expected = [[2.0, 4.0], [6.0, 8.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_multiply_identity(self, small_matrix):
        """Test multiplication by 1.0 returns same matrix."""
        result = forzium_engine.multiply(small_matrix, 1.0)
        pytest.assert_matrices_equal(result, small_matrix)

    def test_multiply_zero(self, small_matrix):
        """Test multiplication by 0.0 returns zero matrix."""
        result = forzium_engine.multiply(small_matrix, 0.0)
        expected = [[0.0, 0.0], [0.0, 0.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_multiply_negative(self, small_matrix):
        """Test multiplication by negative factor."""
        result = forzium_engine.multiply(small_matrix, -1.0)
        expected = [[-1.0, -2.0], [-3.0, -4.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_multiply_large_factor(self, small_matrix):
        """Test multiplication by large factor."""
        result = forzium_engine.multiply(small_matrix, 1e10)
        expected = [[1e10, 2e10], [3e10, 4e10]]
        pytest.assert_matrices_equal(result, expected, rtol=1e-5)

    def test_add_basic(self, small_matrix):
        """Test matrix scalar addition."""
        result = forzium_engine.add(small_matrix, 10.0)
        expected = [[11.0, 12.0], [13.0, 14.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_add_zero(self, small_matrix):
        """Test addition by 0.0 returns same matrix."""
        result = forzium_engine.add(small_matrix, 0.0)
        pytest.assert_matrices_equal(result, small_matrix)

    def test_add_negative(self, small_matrix):
        """Test addition of negative value."""
        result = forzium_engine.add(small_matrix, -5.0)
        expected = [[-4.0, -3.0], [-2.0, -1.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_transpose_square(self, small_matrix):
        """Test transpose of square matrix."""
        result = forzium_engine.transpose(small_matrix)
        expected = [[1.0, 3.0], [2.0, 4.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_transpose_rectangular(self):
        """Test transpose of non-square matrix."""
        matrix = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        result = forzium_engine.transpose(matrix)
        expected = [[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_transpose_single_row(self):
        """Test transpose of single row matrix."""
        matrix = [[1.0, 2.0, 3.0]]
        result = forzium_engine.transpose(matrix)
        expected = [[1.0], [2.0], [3.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_transpose_single_column(self):
        """Test transpose of single column matrix."""
        matrix = [[1.0], [2.0], [3.0]]
        result = forzium_engine.transpose(matrix)
        expected = [[1.0, 2.0, 3.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_transpose_double_transpose(self, small_matrix):
        """Test that double transpose returns original matrix."""
        result = forzium_engine.transpose(forzium_engine.transpose(small_matrix))
        pytest.assert_matrices_equal(result, small_matrix)


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestMatrixMultiplication:
    """Test matrix multiplication operations."""

    def test_matmul_basic(self):
        """Test basic matrix multiplication."""
        a = [[1.0, 2.0], [3.0, 4.0]]
        b = [[5.0, 6.0], [7.0, 8.0]]
        result = forzium_engine.matmul(a, b)
        expected = [[19.0, 22.0], [43.0, 50.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_matmul_identity(self, identity_matrix):
        """Test multiplication with identity matrix."""
        a = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
        result = forzium_engine.matmul(a, identity_matrix)
        pytest.assert_matrices_equal(result, a)

    def test_matmul_zero(self, zero_matrix):
        """Test multiplication with zero matrix."""
        a = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
        result = forzium_engine.matmul(a, zero_matrix)
        pytest.assert_matrices_equal(result, zero_matrix)

    def test_matmul_non_square(self):
        """Test multiplication of non-square matrices."""
        a = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]  # 2x3
        b = [[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]  # 3x2
        result = forzium_engine.matmul(a, b)
        expected = [[58.0, 64.0], [139.0, 154.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_simd_matmul_basic(self):
        """Test SIMD matrix multiplication."""
        a = [[1.0, 2.0], [3.0, 4.0]]
        b = [[5.0, 6.0], [7.0, 8.0]]
        result = forzium_engine.simd_matmul(a, b)
        expected = [[19.0, 22.0], [43.0, 50.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_simd_matmul_matches_regular(self, medium_matrix):
        """Test that SIMD and regular matmul produce same results."""
        regular_result = forzium_engine.matmul(medium_matrix, medium_matrix)
        simd_result = forzium_engine.simd_matmul(medium_matrix, medium_matrix)
        pytest.assert_matrices_equal(regular_result, simd_result, rtol=1e-10)

    def test_matmul_associative(self):
        """Test that matrix multiplication is associative."""
        a = [[1.0, 2.0], [3.0, 4.0]]
        b = [[5.0, 6.0], [7.0, 8.0]]
        c = [[9.0, 10.0], [11.0, 12.0]]
        
        # (AB)C
        ab = forzium_engine.matmul(a, b)
        abc1 = forzium_engine.matmul(ab, c)
        
        # A(BC)
        bc = forzium_engine.matmul(b, c)
        abc2 = forzium_engine.matmul(a, bc)
        
        pytest.assert_matrices_equal(abc1, abc2)


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestElementwiseOperations:
    """Test elementwise operations."""

    def test_elementwise_add_basic(self):
        """Test basic elementwise addition."""
        a = [[1.0, 2.0], [3.0, 4.0]]
        b = [[5.0, 6.0], [7.0, 8.0]]
        result = forzium_engine.elementwise_add(a, b)
        expected = [[6.0, 8.0], [10.0, 12.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_elementwise_add_zero(self, small_matrix, zero_matrix):
        """Test elementwise addition with zero matrix."""
        # Need to ensure same size
        zero = [[0.0, 0.0], [0.0, 0.0]]
        result = forzium_engine.elementwise_add(small_matrix, zero)
        pytest.assert_matrices_equal(result, small_matrix)

    def test_simd_elementwise_add_basic(self):
        """Test SIMD elementwise addition."""
        a = [[1.0, 2.0], [3.0, 4.0]]
        b = [[5.0, 6.0], [7.0, 8.0]]
        result = forzium_engine.simd_elementwise_add(a, b)
        expected = [[6.0, 8.0], [10.0, 12.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_simd_elementwise_add_matches_regular(self, medium_matrix):
        """Test that SIMD and regular elementwise add produce same results."""
        a = medium_matrix
        b = [[float(i * 10 + j + 100) for j in range(10)] for i in range(10)]
        
        regular_result = forzium_engine.elementwise_add(a, b)
        simd_result = forzium_engine.simd_elementwise_add(a, b)
        pytest.assert_matrices_equal(regular_result, simd_result)

    def test_elementwise_mul_basic(self):
        """Test elementwise multiplication (Hadamard product)."""
        a = [[1.0, 2.0], [3.0, 4.0]]
        b = [[5.0, 6.0], [7.0, 8.0]]
        result = forzium_engine.elementwise_mul(a, b)
        expected = [[5.0, 12.0], [21.0, 32.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_elementwise_mul_identity(self, small_matrix):
        """Test elementwise multiplication with ones."""
        ones = [[1.0, 1.0], [1.0, 1.0]]
        result = forzium_engine.elementwise_mul(small_matrix, ones)
        pytest.assert_matrices_equal(result, small_matrix)

    def test_elementwise_mul_zero(self, small_matrix):
        """Test elementwise multiplication with zeros."""
        zeros = [[0.0, 0.0], [0.0, 0.0]]
        result = forzium_engine.elementwise_mul(small_matrix, zeros)
        pytest.assert_matrices_equal(result, zeros)


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestConvolutionOperations:
    """Test convolution and pooling operations."""

    def test_conv2d_basic(self):
        """Test basic 2D convolution."""
        input_matrix = [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ]
        kernel = [[1.0, 0.0], [0.0, 1.0]]
        result = forzium_engine.conv2d(input_matrix, kernel)
        expected = [[6.0, 8.0], [12.0, 14.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_conv2d_identity_kernel(self):
        """Test convolution with identity kernel."""
        input_matrix = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
        kernel = [[1.0]]
        result = forzium_engine.conv2d(input_matrix, kernel)
        pytest.assert_matrices_equal(result, input_matrix)

    def test_conv2d_edge_detection(self):
        """Test convolution with edge detection kernel."""
        input_matrix = [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0, 0.0],
            [0.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
        ]
        # Simple edge detection kernel
        kernel = [[-1.0, -1.0], [-1.0, 3.0]]
        result = forzium_engine.conv2d(input_matrix, kernel)
        # Should detect edges
        assert len(result) == 3
        assert len(result[0]) == 3

    def test_max_pool2d_basic(self):
        """Test basic 2D max pooling."""
        input_matrix = [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ]
        result = forzium_engine.max_pool2d(input_matrix, 2)
        expected = [[6.0, 8.0], [14.0, 16.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_max_pool2d_size_1(self):
        """Test max pooling with size 1 (identity operation)."""
        input_matrix = [[1.0, 2.0], [3.0, 4.0]]
        result = forzium_engine.max_pool2d(input_matrix, 1)
        pytest.assert_matrices_equal(result, input_matrix)

    def test_max_pool2d_negative_values(self):
        """Test max pooling with negative values."""
        input_matrix = [
            [-1.0, -2.0, -3.0, -4.0],
            [-5.0, -6.0, -7.0, -8.0],
            [-9.0, -10.0, -11.0, -12.0],
            [-13.0, -14.0, -15.0, -16.0],
        ]
        result = forzium_engine.max_pool2d(input_matrix, 2)
        expected = [[-1.0, -3.0], [-9.0, -11.0]]
        pytest.assert_matrices_equal(result, expected)


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestDataTransformOperations:
    """Test data transformation operations."""

    def test_scale_basic(self, vector_1d):
        """Test vector scaling."""
        result = forzium_engine.scale(vector_1d, 2.0)
        expected = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
        pytest.assert_vectors_equal(result, expected)

    def test_scale_zero(self, vector_1d):
        """Test scaling by zero."""
        result = forzium_engine.scale(vector_1d, 0.0)
        expected = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        pytest.assert_vectors_equal(result, expected)

    def test_scale_negative(self, vector_1d):
        """Test scaling by negative factor."""
        result = forzium_engine.scale(vector_1d, -1.0)
        expected = [-1.0, -2.0, -3.0, -4.0, -5.0, -6.0]
        pytest.assert_vectors_equal(result, expected)

    def test_normalize_basic(self):
        """Test vector normalization."""
        vector = [3.0, 4.0]
        result = forzium_engine.normalize(vector)
        expected = [0.6, 0.8]
        pytest.assert_vectors_equal(result, expected)

    def test_normalize_unit_vector(self):
        """Test normalizing an already unit vector."""
        vector = [1.0, 0.0, 0.0]
        result = forzium_engine.normalize(vector)
        pytest.assert_vectors_equal(result, vector)

    def test_normalize_magnitude(self):
        """Test that normalized vector has magnitude 1."""
        vector = [1.0, 2.0, 3.0, 4.0]
        result = forzium_engine.normalize(vector)
        magnitude = math.sqrt(sum(x * x for x in result))
        assert abs(magnitude - 1.0) < 1e-9

    def test_reshape_basic(self, vector_1d):
        """Test vector reshaping to matrix."""
        result = forzium_engine.reshape(vector_1d, 2, 3)
        expected = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_reshape_single_row(self, vector_1d):
        """Test reshaping to single row."""
        result = forzium_engine.reshape(vector_1d, 1, 6)
        expected = [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]]
        pytest.assert_matrices_equal(result, expected)

    def test_reshape_single_column(self, vector_1d):
        """Test reshaping to single column."""
        result = forzium_engine.reshape(vector_1d, 6, 1)
        expected = [[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]]
        pytest.assert_matrices_equal(result, expected)


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestUtilityFunctions:
    """Test utility and helper functions."""

    def test_noop(self):
        """Test noop function succeeds."""
        result = forzium_engine.noop()
        assert result is None

    def test_echo_u64_basic(self):
        """Test echoing u64 values."""
        assert forzium_engine.echo_u64(42) == 42
        assert forzium_engine.echo_u64(0) == 0
        assert forzium_engine.echo_u64(2**32) == 2**32

    def test_echo_u64_max_value(self):
        """Test echoing maximum u64 value."""
        max_u64 = 2**64 - 1
        assert forzium_engine.echo_u64(max_u64) == max_u64

    def test_trigger_panic(self):
        """Test that trigger_panic raises an exception."""
        with pytest.raises(Exception):
            forzium_engine.trigger_panic()

    def test_force_gc(self):
        """Test force garbage collection."""
        result = forzium_engine.force_gc()
        # Should complete without error
        assert result is None or isinstance(result, int)


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestRayonMetrics:
    """Test Rayon thread pool metrics."""

    def test_rayon_pool_metrics_structure(self):
        """Test that rayon_pool_metrics returns expected structure."""
        metrics = forzium_engine.rayon_pool_metrics()
        
        expected_keys = {
            "observed_threads",
            "max_active_threads",
            "mean_active_threads",
            "utilization_percent",
            "peak_saturation",
            "total_tasks_started",
            "total_tasks_completed",
            "mean_task_duration_us",
            "max_task_duration_us",
            "min_task_duration_us",
            "busy_time_seconds",
            "observation_seconds",
        }
        
        assert set(metrics.keys()) == expected_keys

    def test_rayon_pool_metrics_types(self):
        """Test that rayon_pool_metrics returns correct types."""
        metrics = forzium_engine.rayon_pool_metrics()
        
        assert isinstance(metrics["observed_threads"], int)
        assert isinstance(metrics["max_active_threads"], int)
        assert isinstance(metrics["mean_active_threads"], float)
        assert isinstance(metrics["utilization_percent"], float)
        assert isinstance(metrics["peak_saturation"], float)

    def test_rayon_pool_metrics_reset(self, medium_matrix):
        """Test rayon_pool_metrics with reset flag."""
        # Perform some operations to generate metrics
        forzium_engine.matmul(medium_matrix, medium_matrix)
        
        # Get metrics with reset
        metrics = forzium_engine.rayon_pool_metrics(reset=True)
        assert metrics["total_tasks_completed"] > 0
        
        # Get metrics again - should be reset
        metrics2 = forzium_engine.rayon_pool_metrics()
        # Note: might not be exactly 0 if operations happened between calls

    def test_rayon_pool_metrics_after_operations(self, large_matrix):
        """Test that metrics are updated after operations."""
        # Reset metrics
        forzium_engine.rayon_pool_metrics(reset=True)
        
        # Perform operations
        forzium_engine.matmul(large_matrix, large_matrix)
        
        # Check metrics
        metrics = forzium_engine.rayon_pool_metrics()
        assert metrics["total_tasks_completed"] > 0
        assert metrics["busy_time_seconds"] > 0


@pytest.mark.unit
@pytest.mark.rust_ffi
class TestAPIBindings:
    """Test API binding functions."""

    def test_sum_list_basic(self):
        """Test sum_list with basic input."""
        result = forzium_engine.sum_list([1, 2, 3, 4, 5])
        assert result == 15

    def test_sum_list_single_element(self):
        """Test sum_list with single element."""
        result = forzium_engine.sum_list([42])
        assert result == 42

    def test_sum_list_negative_numbers(self):
        """Test sum_list with negative numbers."""
        result = forzium_engine.sum_list([-1, -2, -3])
        assert result == -6

    def test_sum_list_mixed_numbers(self):
        """Test sum_list with mixed positive and negative."""
        result = forzium_engine.sum_list([10, -5, 3, -2])
        assert result == 6

    def test_echo_list_basic(self):
        """Test echo_list with basic input."""
        input_list = [1, 2, 3, 4, 5]
        result = forzium_engine.echo_list(input_list)
        assert result == input_list

    def test_echo_list_empty(self):
        """Test echo_list with empty list."""
        result = forzium_engine.echo_list([])
        assert result == []

    def test_echo_list_large_numbers(self):
        """Test echo_list with large numbers."""
        input_list = [2**32, 2**40, 2**50]
        result = forzium_engine.echo_list(input_list)
        assert result == input_list
