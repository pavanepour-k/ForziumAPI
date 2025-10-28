"""
Edge case and error condition tests for Rust FFI functions.

Tests boundary conditions, invalid inputs, and error handling
across all Rust functions exposed to Python.
"""

import pytest
import sys

try:
    import forzium_engine
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="Rust engine not available")


@pytest.mark.edge_case
@pytest.mark.error_handling
class TestMatrixValidationErrors:
    """Test matrix validation error conditions."""

    def test_multiply_empty_matrix(self, empty_matrix):
        """Test multiply with empty matrix raises error."""
        with pytest.raises(Exception) as exc_info:
            forzium_engine.multiply(empty_matrix, 2.0)
        assert "empty" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    def test_multiply_empty_row(self, empty_row_matrix):
        """Test multiply with empty row raises error."""
        with pytest.raises(Exception) as exc_info:
            forzium_engine.multiply(empty_row_matrix, 2.0)
        assert "empty" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    def test_multiply_ragged_matrix(self, ragged_matrix):
        """Test multiply with ragged matrix raises error."""
        with pytest.raises(Exception) as exc_info:
            forzium_engine.multiply(ragged_matrix, 2.0)
        assert "ragged" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    def test_add_empty_matrix(self, empty_matrix):
        """Test add with empty matrix raises error."""
        with pytest.raises(Exception):
            forzium_engine.add(empty_matrix, 10.0)

    def test_add_ragged_matrix(self, ragged_matrix):
        """Test add with ragged matrix raises error."""
        with pytest.raises(Exception):
            forzium_engine.add(ragged_matrix, 10.0)

    def test_transpose_empty_matrix(self, empty_matrix):
        """Test transpose with empty matrix raises error."""
        with pytest.raises(Exception):
            forzium_engine.transpose(empty_matrix)

    def test_transpose_empty_row(self, empty_row_matrix):
        """Test transpose with empty row raises error."""
        with pytest.raises(Exception):
            forzium_engine.transpose(empty_row_matrix)


@pytest.mark.edge_case
@pytest.mark.error_handling
class TestMatmulErrors:
    """Test matrix multiplication error conditions."""

    def test_matmul_shape_mismatch(self):
        """Test matmul with incompatible shapes."""
        a = [[1.0, 2.0]]  # 1x2
        b = [[1.0], [2.0], [3.0]]  # 3x1
        with pytest.raises(Exception) as exc_info:
            forzium_engine.matmul(a, b)
        assert "shape" in str(exc_info.value).lower() or "mismatch" in str(exc_info.value).lower()

    def test_matmul_empty_first_matrix(self, small_matrix):
        """Test matmul with empty first matrix."""
        with pytest.raises(Exception):
            forzium_engine.matmul([], small_matrix)

    def test_matmul_empty_second_matrix(self, small_matrix):
        """Test matmul with empty second matrix."""
        with pytest.raises(Exception):
            forzium_engine.matmul(small_matrix, [])

    def test_matmul_ragged_first_matrix(self, ragged_matrix, small_matrix):
        """Test matmul with ragged first matrix."""
        with pytest.raises(Exception):
            forzium_engine.matmul(ragged_matrix, small_matrix)

    def test_matmul_ragged_second_matrix(self, small_matrix, ragged_matrix):
        """Test matmul with ragged second matrix."""
        with pytest.raises(Exception):
            forzium_engine.matmul(small_matrix, ragged_matrix)

    def test_simd_matmul_shape_mismatch(self):
        """Test SIMD matmul with incompatible shapes."""
        a = [[1.0, 2.0, 3.0]]
        b = [[1.0], [2.0]]
        with pytest.raises(Exception):
            forzium_engine.simd_matmul(a, b)

    def test_simd_matmul_empty_matrix(self):
        """Test SIMD matmul with empty matrix."""
        with pytest.raises(Exception):
            forzium_engine.simd_matmul([], [[1.0]])


@pytest.mark.edge_case
@pytest.mark.error_handling
class TestElementwiseErrors:
    """Test elementwise operation error conditions."""

    def test_elementwise_add_shape_mismatch(self):
        """Test elementwise_add with different shapes."""
        a = [[1.0, 2.0], [3.0, 4.0]]  # 2x2
        b = [[1.0, 2.0, 3.0]]  # 1x3
        with pytest.raises(Exception) as exc_info:
            forzium_engine.elementwise_add(a, b)
        assert "shape" in str(exc_info.value).lower() or "mismatch" in str(exc_info.value).lower()

    def test_elementwise_add_different_rows(self):
        """Test elementwise_add with different row counts."""
        a = [[1.0, 2.0]]
        b = [[1.0, 2.0], [3.0, 4.0]]
        with pytest.raises(Exception):
            forzium_engine.elementwise_add(a, b)

    def test_elementwise_add_different_cols(self):
        """Test elementwise_add with different column counts."""
        a = [[1.0, 2.0], [3.0, 4.0]]
        b = [[1.0], [2.0]]
        with pytest.raises(Exception):
            forzium_engine.elementwise_add(a, b)

    def test_simd_elementwise_add_shape_mismatch(self):
        """Test SIMD elementwise_add with shape mismatch."""
        a = [[1.0, 2.0]]
        b = [[1.0]]
        with pytest.raises(Exception):
            forzium_engine.simd_elementwise_add(a, b)

    def test_elementwise_mul_shape_mismatch(self):
        """Test elementwise_mul with different shapes."""
        a = [[1.0, 2.0]]
        b = [[1.0, 2.0], [3.0, 4.0]]
        with pytest.raises(Exception):
            forzium_engine.elementwise_mul(a, b)


@pytest.mark.edge_case
@pytest.mark.error_handling
class TestConvolutionErrors:
    """Test convolution and pooling error conditions."""

    def test_conv2d_kernel_too_large(self):
        """Test conv2d when kernel is larger than input."""
        input_matrix = [[1.0, 2.0], [3.0, 4.0]]  # 2x2
        kernel = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]  # 3x3
        with pytest.raises(Exception) as exc_info:
            forzium_engine.conv2d(input_matrix, kernel)
        assert "kernel" in str(exc_info.value).lower() or "larger" in str(exc_info.value).lower()

    def test_conv2d_empty_input(self):
        """Test conv2d with empty input."""
        kernel = [[1.0]]
        with pytest.raises(Exception):
            forzium_engine.conv2d([], kernel)

    def test_conv2d_empty_kernel(self):
        """Test conv2d with empty kernel."""
        input_matrix = [[1.0, 2.0], [3.0, 4.0]]
        with pytest.raises(Exception):
            forzium_engine.conv2d(input_matrix, [])

    def test_conv2d_ragged_input(self, ragged_matrix):
        """Test conv2d with ragged input."""
        kernel = [[1.0]]
        with pytest.raises(Exception):
            forzium_engine.conv2d(ragged_matrix, kernel)

    def test_max_pool2d_size_zero(self):
        """Test max_pool2d with size 0."""
        input_matrix = [[1.0, 2.0], [3.0, 4.0]]
        with pytest.raises(Exception) as exc_info:
            forzium_engine.max_pool2d(input_matrix, 0)
        assert "pool" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_max_pool2d_size_not_divisor(self):
        """Test max_pool2d when size doesn't divide dimensions."""
        input_matrix = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]  # 3x3
        with pytest.raises(Exception):
            forzium_engine.max_pool2d(input_matrix, 2)  # 2 doesn't divide 3

    def test_max_pool2d_empty_matrix(self):
        """Test max_pool2d with empty matrix."""
        with pytest.raises(Exception):
            forzium_engine.max_pool2d([], 2)


@pytest.mark.edge_case
@pytest.mark.error_handling
class TestDataTransformErrors:
    """Test data transformation error conditions."""

    def test_scale_empty_vector(self):
        """Test scale with empty vector."""
        with pytest.raises(Exception):
            forzium_engine.scale([], 2.0)

    def test_normalize_empty_vector(self):
        """Test normalize with empty vector."""
        with pytest.raises(Exception):
            forzium_engine.normalize([])

    def test_normalize_zero_vector(self, vector_zeros):
        """Test normalize with all-zero vector."""
        # This should either raise an error or return a zero vector
        # depending on implementation
        try:
            result = forzium_engine.normalize(vector_zeros)
            # If it doesn't raise, check the result
            # It might return zeros or NaN
            assert len(result) == len(vector_zeros)
        except Exception:
            # Expected behavior - can't normalize zero vector
            pass

    def test_reshape_size_mismatch(self):
        """Test reshape when rows*cols doesn't match vector length."""
        vector = [1.0, 2.0, 3.0, 4.0, 5.0]  # length 5
        with pytest.raises(Exception):
            forzium_engine.reshape(vector, 2, 3)  # 2*3 = 6 != 5

    def test_reshape_empty_vector(self):
        """Test reshape with empty vector."""
        with pytest.raises(Exception):
            forzium_engine.reshape([], 2, 2)

    def test_reshape_zero_dimensions(self):
        """Test reshape with zero dimensions."""
        vector = [1.0, 2.0, 3.0, 4.0]
        with pytest.raises(Exception):
            forzium_engine.reshape(vector, 0, 4)
        with pytest.raises(Exception):
            forzium_engine.reshape(vector, 4, 0)


@pytest.mark.edge_case
@pytest.mark.error_handling
class TestAPIBindingErrors:
    """Test API binding error conditions."""

    def test_sum_list_empty(self):
        """Test sum_list with empty list."""
        with pytest.raises(Exception) as exc_info:
            forzium_engine.sum_list([])
        assert "empty" in str(exc_info.value).lower()

    def test_echo_u64_negative(self):
        """Test echo_u64 with negative number."""
        # Should raise error since u64 is unsigned
        with pytest.raises((OverflowError, ValueError, TypeError)):
            forzium_engine.echo_u64(-1)

    def test_echo_u64_too_large(self):
        """Test echo_u64 with number larger than u64 max."""
        too_large = 2**64
        with pytest.raises((OverflowError, ValueError)):
            forzium_engine.echo_u64(too_large)

    def test_echo_u64_float(self):
        """Test echo_u64 with float input."""
        with pytest.raises((TypeError, ValueError)):
            forzium_engine.echo_u64(3.14)

    def test_echo_u64_string(self):
        """Test echo_u64 with string input."""
        with pytest.raises(TypeError):
            forzium_engine.echo_u64("42")


@pytest.mark.edge_case
class TestBoundaryValues:
    """Test boundary and extreme values."""

    def test_multiply_infinity(self):
        """Test multiply with infinity."""
        matrix = [[1.0, 2.0]]
        result = forzium_engine.multiply(matrix, float('inf'))
        assert result[0][0] == float('inf')
        assert result[0][1] == float('inf')

    def test_multiply_negative_infinity(self):
        """Test multiply with negative infinity."""
        matrix = [[1.0, 2.0]]
        result = forzium_engine.multiply(matrix, float('-inf'))
        assert result[0][0] == float('-inf')
        assert result[0][1] == float('-inf')

    def test_add_very_large_number(self):
        """Test add with very large number."""
        matrix = [[1.0]]
        result = forzium_engine.add(matrix, 1e308)
        assert result[0][0] > 1e308

    def test_multiply_very_small_number(self):
        """Test multiply with very small number."""
        matrix = [[1.0, 2.0]]
        result = forzium_engine.multiply(matrix, 1e-308)
        assert 0 < result[0][0] < 1e-307

    def test_matmul_large_dimension(self):
        """Test matmul with large dimension matrices."""
        size = 500
        a = [[1.0] * size for _ in range(size)]
        b = [[1.0] * size for _ in range(size)]
        # Should complete without error
        result = forzium_engine.matmul(a, b)
        assert len(result) == size
        assert len(result[0]) == size

    def test_single_element_matrix(self):
        """Test operations on 1x1 matrix."""
        matrix = [[42.0]]
        
        result = forzium_engine.multiply(matrix, 2.0)
        assert result == [[84.0]]
        
        result = forzium_engine.add(matrix, 10.0)
        assert result == [[52.0]]
        
        result = forzium_engine.transpose(matrix)
        assert result == [[42.0]]
        
        result = forzium_engine.matmul(matrix, matrix)
        assert result == [[1764.0]]

    def test_very_wide_matrix(self):
        """Test operations on very wide matrix (1 row, many columns)."""
        matrix = [[float(i) for i in range(1000)]]
        
        result = forzium_engine.multiply(matrix, 2.0)
        assert len(result) == 1
        assert len(result[0]) == 1000
        assert result[0][0] == 0.0
        assert result[0][999] == 1998.0

    def test_very_tall_matrix(self):
        """Test operations on very tall matrix (many rows, 1 column)."""
        matrix = [[float(i)] for i in range(1000)]
        
        result = forzium_engine.multiply(matrix, 2.0)
        assert len(result) == 1000
        assert len(result[0]) == 1
        assert result[0][0] == 0.0
        assert result[999][0] == 1998.0

    def test_normalize_single_element(self):
        """Test normalize with single element vector."""
        result = forzium_engine.normalize([5.0])
        assert abs(result[0] - 1.0) < 1e-9

    def test_normalize_very_large_values(self):
        """Test normalize with very large values."""
        vector = [1e100, 1e100]
        result = forzium_engine.normalize(vector)
        # Should normalize to approximately [0.707, 0.707]
        import math
        expected = 1.0 / math.sqrt(2.0)
        assert abs(result[0] - expected) < 1e-6
        assert abs(result[1] - expected) < 1e-6


@pytest.mark.edge_case
class TestSpecialFloatValues:
    """Test handling of NaN and special float values."""

    def test_multiply_with_nan(self):
        """Test multiply with NaN values."""
        matrix = [[1.0, float('nan')]]
        result = forzium_engine.multiply(matrix, 2.0)
        assert result[0][0] == 2.0
        assert result[0][1] != result[0][1]  # NaN != NaN

    def test_add_with_nan(self):
        """Test add with NaN values."""
        matrix = [[1.0, float('nan')]]
        result = forzium_engine.add(matrix, 10.0)
        assert result[0][0] == 11.0
        assert result[0][1] != result[0][1]  # NaN != NaN

    def test_matmul_with_nan(self):
        """Test matmul with NaN values."""
        a = [[1.0, float('nan')]]
        b = [[1.0], [1.0]]
        result = forzium_engine.matmul(a, b)
        # Result should contain NaN
        assert result[0][0] != result[0][0]  # NaN != NaN

    def test_normalize_with_inf(self):
        """Test normalize with infinity."""
        vector = [float('inf'), 1.0]
        try:
            result = forzium_engine.normalize(vector)
            # If it doesn't raise, result should have inf
        except Exception:
            # Also acceptable to raise an error
            pass


@pytest.mark.edge_case
class TestTypeCoercion:
    """Test type coercion and conversion."""

    def test_multiply_with_integers(self):
        """Test multiply accepts integer matrices."""
        matrix = [[1, 2], [3, 4]]  # Python integers
        result = forzium_engine.multiply(matrix, 2.0)
        # Should convert to float internally
        assert result == [[2.0, 4.0], [6.0, 8.0]]

    def test_multiply_with_mixed_types(self):
        """Test multiply with mixed int/float."""
        matrix = [[1, 2.0], [3, 4.0]]
        result = forzium_engine.multiply(matrix, 2)
        assert result == [[2.0, 4.0], [6.0, 8.0]]

    def test_scale_with_integers(self):
        """Test scale accepts integer vector."""
        vector = [1, 2, 3, 4, 5]
        result = forzium_engine.scale(vector, 2.0)
        assert result == [2.0, 4.0, 6.0, 8.0, 10.0]

    def test_echo_list_preserves_values(self):
        """Test echo_list preserves large integer values."""
        large_values = [2**32 - 1, 2**40, 2**50]
        result = forzium_engine.echo_list(large_values)
        assert result == large_values
