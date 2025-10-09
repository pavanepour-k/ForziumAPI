"""Business logic coordinating computation operations"""

import time
from array import array
from typing import Any, Dict, Iterable, List, cast

from interfaces.shared_types import CancellationToken

try:  # pragma: no cover - optional extension
    from forzium_engine import PoolAllocator  # type: ignore
except Exception:  # pragma: no cover
    # Broad exception handling for optional dependency import
    # to provide fallback implementation when Rust extension unavailable

    class PoolAllocator:  # type: ignore
        """Fallback variable-size pool capped by total capacity."""

        def __init__(self, capacity: int) -> None:
            self.capacity = capacity
            self.free: list[bytearray] = []
            self.used = 0

        def allocate(self, size: int) -> bytearray:
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
            self.used -= len(block)
            self.free.append(block)

        def available(self) -> int:
            return self.capacity - self.used


try:
    import forzium_engine

    ENGINE: forzium_engine.ComputeEngine | None = forzium_engine.ComputeEngine()
except ImportError:  # pragma: no cover
    ENGINE = None

    class _PyOps:
        @staticmethod
        def multiply(matrix: List[List[float]], factor: float) -> List[List[float]]:
            return [[x * factor for x in row] for row in matrix]

        @staticmethod
        def add(matrix: List[List[float]], addend: float) -> List[List[float]]:
            return [[x + addend for x in row] for row in matrix]

        @staticmethod
        def matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
            if not a or not b or len(a[0]) != len(b):
                raise ValueError("Incompatible matrices")
            cols = len(b[0])
            result = [[0.0 for _ in range(cols)] for _ in range(len(a))]
            for i, row in enumerate(a):
                for k, val in enumerate(row):
                    for j in range(cols):
                        result[i][j] += val * b[k][j]
            return result

        @staticmethod
        def force_gc() -> None:
            import gc

            gc.collect()

    forzium_engine = _PyOps()  # type: ignore[assignment]


def run_computation(
    data: List[List[float]],
    operation: str,
    parameters: Dict[str, Any],
    token: CancellationToken | None = None,
) -> Dict[str, Any]:
    """Execute a simple arithmetic operation on a matrix"""
    start = time.time()

    if token and token.cancelled():
        raise RuntimeError("operation cancelled")

    try:
        if ENGINE and ENGINE.supports(operation):
            result = ENGINE.compute(
                data,
                operation,
                parameters,
                token.cancelled() if token else False,
            )
        elif operation == "multiply":
            factor = float(parameters.get("factor", 1))
            result = forzium_engine.multiply(data, factor)
        elif operation == "add":
            addend = float(parameters.get("addend", 0))
            result = forzium_engine.add(data, addend)
        elif operation == "matmul":
            other = parameters.get("matrix_b")
            if not isinstance(other, list):
                raise ValueError("matrix_b parameter required")
            result = forzium_engine.matmul(data, other)
        else:
            raise ValueError("Unsupported operation")
    except ValueError:
        raise
    except Exception as exc:  # pragma: no cover - simple mapping
        # Catch-all for unexpected errors in compute operations
        # Convert to RuntimeError for consistent error handling
        raise RuntimeError(f"{operation} failed: {exc}") from exc

    exec_ms = (time.time() - start) * 1000
    return {
        "result": result,
        "execution_time_ms": exec_ms,
        "memory_usage_mb": 0.0,
        "rust_operations_count": len(result) * len(result[0]) if result else 0,
    }


def stream_computation(
    data: List[List[float]],
    operation: str,
    parameters: Dict[str, Any],
    token: CancellationToken | None = None,
) -> Iterable[List[float]]:
    """Yield computation results row by row"""

    if token and token.cancelled():
        raise RuntimeError("operation cancelled")

    try:
        if ENGINE and ENGINE.supports(operation):
            result = ENGINE.compute(
                data,
                operation,
                parameters,
                token.cancelled() if token else False,
            )
        elif operation == "multiply":
            factor = float(parameters.get("factor", 1))
            result = forzium_engine.multiply(data, factor)
        elif operation == "add":
            addend = float(parameters.get("addend", 0))
            result = forzium_engine.add(data, addend)
        elif operation == "matmul":
            other = parameters.get("matrix_b")
            if not isinstance(other, list):
                raise ValueError("matrix_b parameter required")
            result = forzium_engine.matmul(data, other)
        else:
            raise ValueError("Unsupported operation")
    except ValueError:
        raise
    except Exception as exc:
        # Catch-all for unexpected errors in streaming compute operations
        # Convert to RuntimeError for consistent error handling
        raise RuntimeError(f"{operation} failed: {exc}") from exc

    for row in result:
        if token and token.cancelled():
            raise RuntimeError("operation cancelled")
        yield row


def zero_copy_multiply(
    data: List[List[float]], factor: float, pool: PoolAllocator
) -> memoryview:
    """Multiply *data* by *factor* into a pooled buffer."""

    if pool is None:  # pragma: no cover - defensive
        raise RuntimeError("memory pool unavailable")
    values = array("d", (v * factor for row in data for v in row))
    block = pool.allocate(len(values) * 8)
    view = memoryview(block).cast("d")
    view[:] = values
    return cast(memoryview, view)


def profile_pool(pool: PoolAllocator, workers: int, size: int) -> int:
    """Stress *pool* with concurrent allocations."""

    import threading

    peak = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal peak
        block = pool.allocate(size)
        with lock:
            cap = pool.capacity() if callable(pool.capacity) else pool.capacity
            used = cap - pool.available()
            if used > peak:
                peak = used
        pool.deallocate(block)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return peak
