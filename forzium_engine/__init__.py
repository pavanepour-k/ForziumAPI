"""Forzium Engine - Rust-backed compute engine with Python fallbacks."""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Mapping, Optional

# Try to import the real Rust extension
try:
    import forzium_engine as _rust_engine
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    _rust_engine = None

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