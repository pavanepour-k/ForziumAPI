"""Forzium Engine - Rust-backed compute engine with Python fallbacks."""

from __future__ import annotations

import logging
import os
import warnings
from typing import Any, Dict, List, Mapping, Optional

# Set up logging for performance warnings
_logger = logging.getLogger(__name__)

# Try to import the real Rust extension
try:
    from . import forzium_engine as _rust_engine
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    _rust_engine = None
    # Emit warning on module load when Rust engine unavailable
    warnings.warn(
        "Rust engine not available. Using Python fallback implementations. "
        "Performance will be significantly degraded. "
        "Install the Rust extension with: poetry run maturin develop "
        "--manifest-path core/rust_engine/Cargo.toml",
        UserWarning,
        stacklevel=2
    )

__version__ = "0.1.4"


class ComputeRequestSchema:
    """Schema for validating compute requests."""

    def __init__(self) -> None:
        self.required_keys = ("data", "operation")

    def validate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Validate a compute request payload."""
        missing = [key for key in self.required_keys if key not in payload]
        if missing:
            raise ValueError(
                f"Missing keys for compute request validation: {missing}"
            )
        
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Data must be a non-empty rectangular matrix")
        
        if not isinstance(data[0], list):
            raise ValueError("Data must be a matrix (list of lists)")
            
        row_len = len(data[0])
        for row in data:
            if not isinstance(row, list) or len(row) != row_len:
                raise ValueError("Data must be a non-empty rectangular matrix")
        
        result = dict(payload)
        if "parameters" not in result:
            result["parameters"] = {}
        return result


class ComputeEngine:
    """Compute engine with Rust backend and Python fallbacks."""

    def __init__(self) -> None:
        self._rust_engine = None
        if _RUST_AVAILABLE:
            try:
                self._rust_engine = _rust_engine.ComputeEngine()
            except Exception:
                pass

    def supports(self, operation: str) -> bool:
        """Check if the engine supports the given operation."""
        if self._rust_engine:
            return self._rust_engine.supports(operation)
        return operation in {"multiply", "add", "matmul"}

    def compute(
        self,
        data: List[List[float]],
        operation: str,
        parameters: Dict[str, Any],
        cancel: Optional[bool] = None,
    ) -> List[List[float]]:
        """Execute a computation operation."""
        if cancel:
            raise RuntimeError("operation cancelled")
            
        if self._rust_engine and self._rust_engine.supports(operation):
            return self._rust_engine.compute(data, operation, parameters, cancel)
        
        # Python fallback implementations
        if operation == "multiply":
            factor = float(parameters.get("factor", 1.0))
            return [[x * factor for x in row] for row in data]
        elif operation == "add":
            addend = float(parameters.get("addend", 0.0))
            return [[x + addend for x in row] for row in data]
        elif operation == "matmul":
            other = parameters.get("matrix_b")
            if not isinstance(other, list):
                raise ValueError("matrix_b parameter required")
            return self._matmul_python(data, other)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def _matmul_python(self, a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        """Python implementation of matrix multiplication."""
        if not a or not b or len(a[0]) != len(b):
            raise ValueError("Incompatible matrices")
        
        rows_a, cols_a = len(a), len(a[0])
        rows_b, cols_b = len(b), len(b[0])
        
        result = [[0.0 for _ in range(cols_b)] for _ in range(rows_a)]
        
        for i in range(rows_a):
            for j in range(cols_b):
                for k in range(cols_a):
                    result[i][j] += a[i][k] * b[k][j]
        
        return result


class ForziumHttpServer:
    """HTTP server with Rust backend and Python fallback."""

    def __init__(self) -> None:
        self._rust_server = None
        if _RUST_AVAILABLE:
            try:
                self._rust_server = _rust_engine.ForziumHttpServer()
            except Exception:
                pass

    def serve(self, addr: str) -> None:
        """Start the HTTP server."""
        if self._rust_server:
            return self._rust_server.serve(addr)
        else:
            # Python fallback - for now just raise an error
            raise RuntimeError(
                "Rust HTTP server not available. Please build the Rust extension."
            )

    def shutdown(self) -> None:
        """Shutdown the HTTP server."""
        if self._rust_server:
            return self._rust_server.shutdown()


class PoolAllocator:
    """Memory pool allocator with Rust backend and Python fallback."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.free: List[bytearray] = []
        self.used = 0

    def allocate(self, size: int) -> bytearray:
        """Allocate a block of memory."""
        if self.used + size > self.capacity:
            raise MemoryError("capacity exceeded")
        
        self.used += size
        if self.free:
            block = self.free.pop()
            if len(block) < size:
                block.extend(b"\x00" * (size - len(block)))
            return block[:size]
        return bytearray(size)

    def deallocate(self, block: bytearray) -> None:
        """Deallocate a block of memory."""
        self.used -= len(block)
        self.free.append(block)

    def available(self) -> int:
        """Get available memory."""
        return self.capacity - self.used


# Export all the classes and functions
__all__ = [
    "__version__",
    "ComputeRequestSchema",
    "ComputeEngine", 
    "ForziumHttpServer",
    "PoolAllocator",
]

# Re-export Rust functions when available
if _RUST_AVAILABLE and _rust_engine:
    # Core tensor operations
    multiply = _rust_engine.multiply
    add = _rust_engine.add
    matmul = _rust_engine.matmul
    simd_matmul = _rust_engine.simd_matmul
    transpose = _rust_engine.transpose
    elementwise_add = _rust_engine.elementwise_add
    simd_elementwise_add = _rust_engine.simd_elementwise_add
    elementwise_mul = _rust_engine.elementwise_mul
    conv2d = _rust_engine.conv2d
    max_pool2d = _rust_engine.max_pool2d
    
    # Data transformation
    scale = _rust_engine.scale
    normalize = _rust_engine.normalize
    reshape = _rust_engine.reshape
    
    # Utility functions
    noop = _rust_engine.noop
    echo_u64 = _rust_engine.echo_u64
    force_gc = _rust_engine.force_gc
    rayon_pool_metrics = _rust_engine.rayon_pool_metrics
    trigger_panic = _rust_engine.trigger_panic
    
    # Update __all__ to include Rust functions
    __all__.extend([
        "multiply", "add", "matmul", "simd_matmul", "transpose",
        "elementwise_add", "simd_elementwise_add", "elementwise_mul",
        "conv2d", "max_pool2d", "scale", "normalize", "reshape",
        "noop", "echo_u64", "force_gc", "rayon_pool_metrics", "trigger_panic"
    ])
else:
    # Helper function to emit performance warnings
    def _emit_performance_warning(operation: str, performance_impact: str = "10-100x slower") -> None:
        """Emit a performance warning for Python fallback operations."""
        if not os.getenv("FORZIUM_SUPPRESS_FALLBACK_WARNINGS"):
            warnings.warn(
                f"Using Python fallback for {operation}. "
                f"Performance impact: {performance_impact}. "
                f"Install Rust extension for optimal performance.",
                UserWarning,
                stacklevel=3
            )
    
    # Python fallback implementations
    def multiply(matrix: List[List[float]], factor: float) -> List[List[float]]:
        _emit_performance_warning("matrix multiplication", "5-20x slower")
        return [[x * factor for x in row] for row in matrix]
    
    def add(matrix: List[List[float]], addend: float) -> List[List[float]]:
        _emit_performance_warning("matrix addition", "3-10x slower")
        return [[x + addend for x in row] for row in matrix]
    
    def matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        _emit_performance_warning("matrix multiplication", "10-100x slower")
        if not a or not b or len(a[0]) != len(b):
            raise ValueError("Incompatible matrices")
        cols = len(b[0])
        result = [[0.0 for _ in range(cols)] for _ in range(len(a))]
        for i, row in enumerate(a):
            for k, val in enumerate(row):
                for j in range(cols):
                    result[i][j] += val * b[k][j]
        return result
    
    def simd_matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        _emit_performance_warning("SIMD matrix multiplication", "20-200x slower")
        return matmul(a, b)  # Fallback to regular matmul
    
    def transpose(matrix: List[List[float]]) -> List[List[float]]:
        _emit_performance_warning("matrix transpose", "2-5x slower")
        return list(map(list, zip(*matrix)))
    
    def elementwise_add(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        _emit_performance_warning("elementwise addition", "5-20x slower")
        return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]
    
    def simd_elementwise_add(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        _emit_performance_warning("SIMD elementwise addition", "10-50x slower")
        return elementwise_add(a, b)  # Fallback to regular elementwise_add
    
    def elementwise_mul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        _emit_performance_warning("elementwise multiplication", "5-20x slower")
        return [[a[i][j] * b[i][j] for j in range(len(a[0]))] for i in range(len(a))]
    
    def conv2d(input_: List[List[float]], kernel: List[List[float]]) -> List[List[float]]:
        _emit_performance_warning("2D convolution", "50-500x slower")
        # Simple 2D convolution implementation
        input_h, input_w = len(input_), len(input_[0])
        kernel_h, kernel_w = len(kernel), len(kernel[0])
        output_h = input_h - kernel_h + 1
        output_w = input_w - kernel_w + 1
        
        result = [[0.0 for _ in range(output_w)] for _ in range(output_h)]
        for i in range(output_h):
            for j in range(output_w):
                for ki in range(kernel_h):
                    for kj in range(kernel_w):
                        result[i][j] += input_[i + ki][j + kj] * kernel[ki][kj]
        return result
    
    def max_pool2d(a: List[List[float]], size: int) -> List[List[float]]:
        _emit_performance_warning("max pooling", "10-50x slower")
        # Simple max pooling implementation
        h, w = len(a), len(a[0])
        output_h = h // size
        output_w = w // size
        
        result = [[0.0 for _ in range(output_w)] for _ in range(output_h)]
        for i in range(output_h):
            for j in range(output_w):
                max_val = float('-inf')
                for ki in range(size):
                    for kj in range(size):
                        max_val = max(max_val, a[i * size + ki][j * size + kj])
                result[i][j] = max_val
        return result
    
    def scale(vector: List[float], factor: float) -> List[float]:
        _emit_performance_warning("vector scaling", "2-5x slower")
        return [x * factor for x in vector]
    
    def normalize(vector: List[float]) -> List[float]:
        _emit_performance_warning("vector normalization", "3-10x slower")
        import math
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector] if norm > 0 else vector
    
    def reshape(vector: List[float], rows: int, cols: int) -> List[List[float]]:
        _emit_performance_warning("vector reshape", "2-5x slower")
        if len(vector) != rows * cols:
            raise ValueError("Vector length must equal rows * cols")
        return [vector[i * cols:(i + 1) * cols] for i in range(rows)]
    
    def noop() -> None:
        pass
    
    def echo_u64(value: int) -> int:
        return value
    
    def force_gc() -> None:
        import gc
        gc.collect()
    
    def rayon_pool_metrics(reset: bool = False) -> Dict[str, Any]:
        return {
            "observed_threads": 0,
            "max_active_threads": 0,
            "mean_active_threads": 0.0,
            "utilization_percent": 0.0,
            "peak_saturation": 0.0,
            "total_tasks_started": 0,
            "total_tasks_completed": 0,
            "mean_task_duration_us": 0.0,
            "max_task_duration_us": 0,
            "min_task_duration_us": 0,
            "busy_time_seconds": 0.0,
            "observation_seconds": 0.0,
        }
    
    def trigger_panic() -> None:
        raise RuntimeError("forced panic")
    
    # Update __all__ to include fallback functions
    __all__.extend([
        "multiply", "add", "matmul", "simd_matmul", "transpose",
        "elementwise_add", "simd_elementwise_add", "elementwise_mul",
        "conv2d", "max_pool2d", "scale", "normalize", "reshape",
        "noop", "echo_u64", "force_gc", "rayon_pool_metrics", "trigger_panic"
    ])