"""Business logic coordinating computation operations"""

from typing import Any, Dict, Iterable, List
import time

try:
    import forzium_engine
except ImportError:  # pragma: no cover - fallback for non-compiled environments
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

    forzium_engine = _PyOps()


def run_computation(
    data: List[List[float]], operation: str, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a simple arithmetic operation on a matrix"""
    start = time.time()

    if operation == "multiply":
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

    exec_ms = (time.time() - start) * 1000
    return {
        "result": result,
        "execution_time_ms": exec_ms,
        "memory_usage_mb": 0.0,
        "rust_operations_count": len(result) * len(result[0]) if result else 0,
    }


def stream_computation(
    data: List[List[float]], operation: str, parameters: Dict[str, Any]
) -> Iterable[List[float]]:
    """Yield computation results row by row"""

    if operation == "multiply":
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

    for row in result:
        yield row
        