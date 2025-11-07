"""
Zero-copy operations for high-performance NumPy array processing using the Rust backend.

This module provides functions that operate directly on NumPy arrays without unnecessary data 
copies between Python and Rust, resulting in significant performance improvements for large arrays.
"""

from typing import Literal, Union, TypeAlias
import numpy as np
import numpy.typing as npt

# Define type aliases for better type hinting
NDArrayFloat: TypeAlias = npt.NDArray[np.float64]
OpType = Literal["add", "multiply", "subtract", "divide"]

try:
    from forzium_engine.numpy_ops import (
        zero_copy_multiply,
        zero_copy_conv2d,
        zero_copy_elementwise_op,
        get_zero_copy_ops_count,
    )
except ImportError:
    # Fallback implementations when Rust engine is unavailable
    def zero_copy_multiply(array: NDArrayFloat, factor: float) -> NDArrayFloat:
        """
        Multiply a NumPy array by a factor in-place.
        
        Args:
            array: Input NumPy array
            factor: Multiplication factor
            
        Returns:
            Modified array (same object as input)
        """
        # Note: This is not truly zero-copy in the fallback implementation
        return array * factor
    
    def zero_copy_conv2d(image: NDArrayFloat, kernel: NDArrayFloat) -> NDArrayFloat:
        """
        Apply 2D convolution using zero-copy operations.
        
        Args:
            image: 2D array representing the input image
            kernel: 2D array representing the convolution kernel
            
        Returns:
            Result of convolution operation
            
        Raises:
            ValueError: If kernel dimensions exceed image dimensions
        """
        if kernel.shape[0] > image.shape[0] or kernel.shape[1] > image.shape[1]:
            raise ValueError("Kernel dimensions cannot be larger than image dimensions")
        
        # Pure Python implementation of 2D convolution
        out_rows = image.shape[0] - kernel.shape[0] + 1
        out_cols = image.shape[1] - kernel.shape[1] + 1
        result = np.zeros((out_rows, out_cols), dtype=np.float64)
        
        for i in range(out_rows):
            for j in range(out_cols):
                result[i, j] = np.sum(
                    image[i:i+kernel.shape[0], j:j+kernel.shape[1]] * kernel
                )
        
        return result
    
    def zero_copy_elementwise_op(
        array_a: NDArrayFloat, 
        array_b: NDArrayFloat, 
        operation: OpType
    ) -> NDArrayFloat:
        """
        Perform element-wise operation between two arrays without copying data.
        
        Args:
            array_a: First input array
            array_b: Second input array with same dimensions
            operation: Operation to perform ("add", "multiply", "subtract", "divide")
            
        Returns:
            Result of element-wise operation
            
        Raises:
            ValueError: If arrays have different shapes or operation is invalid
            ZeroDivisionError: If division by zero occurs
        """
        if array_a.shape != array_b.shape:
            raise ValueError(f"Arrays must have the same shape: {array_a.shape} vs {array_b.shape}")
        
        if operation == "add":
            return array_a + array_b
        elif operation == "multiply":
            return array_a * array_b
        elif operation == "subtract":
            return array_a - array_b
        elif operation == "divide":
            if np.any(array_b == 0):
                raise ZeroDivisionError("Division by zero")
            return array_a / array_b
        else:
            raise ValueError("Unsupported operation. Choose from: add, multiply, subtract, divide")
    
    def get_zero_copy_ops_count() -> int:
        """
        Get the count of zero-copy operations performed.
        
        Returns:
            Number of zero-copy operations performed
        """
        return 0


def matrix_multiply_inplace(matrix: NDArrayFloat, factor: float) -> NDArrayFloat:
    """
    Multiply a matrix by a factor in-place using zero-copy operations.
    
    This function modifies the input array directly without creating a copy,
    resulting in significant performance improvements for large arrays.
    
    Args:
        matrix: 2D NumPy array of float64 values
        factor: Multiplication factor
        
    Returns:
        Modified matrix (same object as input)
        
    Examples:
        >>> import numpy as np
        >>> from forzium._ffi.zero_copy import matrix_multiply_inplace
        >>> matrix = np.array([[1.0, 2.0], [3.0, 4.0]])
        >>> result = matrix_multiply_inplace(matrix, 2.0)
        >>> print(result)  # matrix is also modified
        [[2. 4.]
         [6. 8.]]
    """
    return zero_copy_multiply(matrix, factor)


def convolve2d(image: NDArrayFloat, kernel: NDArrayFloat) -> NDArrayFloat:
    """
    Apply 2D convolution using zero-copy operations.
    
    This function applies a convolution kernel to an input image without
    unnecessary memory copies between Python and Rust.
    
    Args:
        image: 2D NumPy array representing the input image
        kernel: 2D NumPy array representing the convolution kernel
        
    Returns:
        Result of convolution operation
        
    Raises:
        ValueError: If kernel dimensions exceed image dimensions
        
    Examples:
        >>> import numpy as np
        >>> from forzium._ffi.zero_copy import convolve2d
        >>> image = np.random.random((10, 10))
        >>> kernel = np.array([[1, 0, -1], [2, 0, -2], [1, 0, -1]])  # Sobel filter
        >>> result = convolve2d(image, kernel)
    """
    return zero_copy_conv2d(image, kernel)


def elementwise_operation(
    array_a: NDArrayFloat, 
    array_b: NDArrayFloat, 
    operation: OpType = "add"
) -> NDArrayFloat:
    """
    Perform element-wise operation between two arrays without copying data.
    
    Args:
        array_a: First input array
        array_b: Second input array with same dimensions
        operation: Operation to perform ("add", "multiply", "subtract", "divide")
        
    Returns:
        Result of element-wise operation
        
    Raises:
        ValueError: If arrays have different shapes or operation is invalid
        ZeroDivisionError: If division by zero occurs
        
    Examples:
        >>> import numpy as np
        >>> from forzium._ffi.zero_copy import elementwise_operation
        >>> a = np.array([[1.0, 2.0], [3.0, 4.0]])
        >>> b = np.array([[5.0, 6.0], [7.0, 8.0]])
        >>> result = elementwise_operation(a, b, "multiply")
        >>> print(result)
        [[ 5. 12.]
         [21. 32.]]
    """
    return zero_copy_elementwise_op(array_a, array_b, operation)


def get_operations_count() -> int:
    """
    Get the count of zero-copy operations performed by the Rust backend.
    
    Returns:
        Number of zero-copy operations performed
        
    Examples:
        >>> from forzium._ffi.zero_copy import get_operations_count, matrix_multiply_inplace
        >>> import numpy as np
        >>> count_before = get_operations_count()
        >>> matrix_multiply_inplace(np.random.random((10, 10)), 2.0)
        >>> count_after = get_operations_count()
        >>> print(f"Operations performed: {count_after - count_before}")
        Operations performed: 1
    """
    return get_zero_copy_ops_count()
