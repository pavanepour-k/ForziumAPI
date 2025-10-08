"""Tests for GPU service functionality."""

import pytest
from unittest.mock import Mock, patch
from core.service.gpu import (
    elementwise_add, elementwise_mul, matmul, conv2d,
    benchmark_elementwise_mul, benchmark_matmul, benchmark_conv2d
)


class TestGPUService:
    """Test GPU service functionality."""

    def test_elementwise_add_cpu_fallback(self):
        """Test elementwise add with CPU fallback."""
        with patch('core.service.gpu.USE_GPU', False):
            a = [[1.0, 2.0], [3.0, 4.0]]
            b = [[5.0, 6.0], [7.0, 8.0]]
            
            result = elementwise_add(a, b)
            assert result == [[6.0, 8.0], [10.0, 12.0]]

    def test_elementwise_mul_cpu_fallback(self):
        """Test elementwise multiplication with CPU fallback."""
        with patch('core.service.gpu.USE_GPU', False):
            a = [[1.0, 2.0], [3.0, 4.0]]
            b = [[5.0, 6.0], [7.0, 8.0]]
            
            result = elementwise_mul(a, b)
            assert result == [[5.0, 12.0], [21.0, 32.0]]

    def test_matmul_cpu_fallback(self):
        """Test matrix multiplication with CPU fallback."""
        with patch('core.service.gpu.USE_GPU', False):
            a = [[1.0, 2.0], [3.0, 4.0]]
            b = [[5.0, 6.0], [7.0, 8.0]]
            
            result = matmul(a, b)
            assert result == [[19.0, 22.0], [43.0, 50.0]]

    def test_conv2d_cpu_fallback(self):
        """Test 2D convolution with CPU fallback."""
        with patch('core.service.gpu.USE_GPU', False):
            input_matrix = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
            kernel = [[1.0, 0.0], [0.0, 1.0]]
            
            result = conv2d(input_matrix, kernel)
            assert len(result) == 2
            assert len(result[0]) == 2

    def test_benchmark_elementwise_mul(self):
        """Test elementwise multiplication benchmark."""
        with patch('core.service.gpu.USE_GPU', False):
            a = [[1.0, 2.0], [3.0, 4.0]]
            b = [[5.0, 6.0], [7.0, 8.0]]
            
            result = benchmark_elementwise_mul(a, b, repeat=1)
            
            assert "cpu_ms" in result
            assert "gpu_ms" in result
            assert result["gpu_ms"] == float("inf")  # GPU not available

    def test_benchmark_matmul(self):
        """Test matrix multiplication benchmark."""
        with patch('core.service.gpu.USE_GPU', False):
            a = [[1.0, 2.0], [3.0, 4.0]]
            b = [[5.0, 6.0], [7.0, 8.0]]
            
            result = benchmark_matmul(a, b, repeat=1)
            
            assert "cpu_ms" in result
            assert "gpu_ms" in result
            assert result["gpu_ms"] == float("inf")  # GPU not available

    def test_benchmark_conv2d(self):
        """Test 2D convolution benchmark."""
        with patch('core.service.gpu.USE_GPU', False):
            a = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
            k = [[1.0, 0.0], [0.0, 1.0]]
            
            result = benchmark_conv2d(a, k, repeat=1)
            
            assert "cpu_ms" in result
            assert "gpu_ms" in result
            assert result["gpu_ms"] == float("inf")  # GPU not available

    def test_gpu_available_simulation(self):
        """Test GPU functionality when GPU is available."""
        with patch('core.service.gpu.USE_GPU', True), \
             patch('core.service.gpu.cp') as mock_cp:
            
            # Mock CuPy functionality
            mock_array = Mock()
            mock_array.__add__ = Mock(return_value=mock_array)
            mock_array.__mul__ = Mock(return_value=mock_array)
            mock_cp.array.return_value = mock_array
            
            # Mock numpy array with tolist method
            mock_numpy_result = Mock()
            mock_numpy_result.tolist.return_value = [[6.0, 8.0], [10.0, 12.0]]
            mock_cp.asnumpy.return_value = mock_numpy_result
            
            a = [[1.0, 2.0], [3.0, 4.0]]
            b = [[5.0, 6.0], [7.0, 8.0]]
            
            result = elementwise_add(a, b)
            assert result == [[6.0, 8.0], [10.0, 12.0]]
