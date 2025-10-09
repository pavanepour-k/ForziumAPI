"""Optional GPU-accelerated tensor helpers.

This module uses CuPy when available and enabled via the
``FORZIUM_USE_GPU`` environment variable. Operations fall back to a
Rust-powered CPU implementation otherwise. A GPU device may be selected
via ``FORZIUM_GPU_DEVICE``.
"""

from __future__ import annotations

import os
import time
import warnings
from typing import List

try:
    import forzium_engine
    _rust_conv2d = forzium_engine.conv2d
    _rust_add = forzium_engine.elementwise_add
    _rust_mul = forzium_engine.elementwise_mul
    _rust_matmul = forzium_engine.simd_matmul
    _RUST_FUNCTIONS_AVAILABLE = True
except (ImportError, AttributeError):
    _rust_conv2d = None
    _rust_add = None
    _rust_mul = None
    _rust_matmul = None
    _RUST_FUNCTIONS_AVAILABLE = False
    # Emit warning when Rust functions are not available
    warnings.warn(
        "Rust compute functions not available in GPU service. "
        "Using Python fallbacks with significant performance impact. "
        "Install Rust extension for optimal performance.",
        UserWarning,
        stacklevel=2
    )

try:  # pragma: no cover - optional dependency
    import cupy as cp  # type: ignore
except ImportError:  # pragma: no cover
    cp = None  # type: ignore
try:  # pragma: no cover - optional dependency
    import cupyx.scipy.signal as cpsignal  # type: ignore
except ImportError:  # pragma: no cover
    cpsignal = None  # type: ignore

GPU_DEVICE = int(os.getenv("FORZIUM_GPU_DEVICE", "0"))
USE_GPU = bool(cp) and os.getenv("FORZIUM_USE_GPU") == "1"


def _emit_gpu_performance_warning(
    operation: str, performance_impact: str = "10-100x slower"
) -> None:
    """Emit a performance warning for GPU service Python fallback operations."""
    if not os.getenv("FORZIUM_SUPPRESS_FALLBACK_WARNINGS"):
        warnings.warn(
            f"Using Python fallback for {operation} in GPU service. "
            f"Performance impact: {performance_impact}. "
            f"Install Rust extension for optimal performance.",
            UserWarning,
            stacklevel=3
        )


if USE_GPU and cp and hasattr(cp, "cuda"):
    try:  # pragma: no cover - optional dependency
        cp.cuda.Device(GPU_DEVICE).use()
    except (RuntimeError, AttributeError):  # pragma: no cover
        USE_GPU = False

if USE_GPU and cp and hasattr(cp, "RawKernel"):
    _ADD_KERNEL = cp.RawKernel(
        r"""
        extern "C" __global__ void elem_add(
            const double* a, const double* b, double* out, const int n
        ) {
            int idx = blockDim.x * blockIdx.x + threadIdx.x;
            if (idx < n) {
                out[idx] = a[idx] + b[idx];
            }
        }
        """,
        "elem_add",
    )
    _MUL_KERNEL = cp.RawKernel(
        r"""
        extern "C" __global__ void elem_mul(
            const double* a, const double* b, double* out, const int n
        ) {
            int idx = blockDim.x * blockIdx.x + threadIdx.x;
            if (idx < n) {
                out[idx] = a[idx] * b[idx];
            }
        }
        """,
        "elem_mul",
    )
else:  # pragma: no cover - simple fallback
    _ADD_KERNEL = _MUL_KERNEL = None


def elementwise_add(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Add matrices *a* and *b* using CUDA when available."""

    if USE_GPU and cp:
        a_cp = cp.array(a)
        b_cp = cp.array(b)
        result = cp.asnumpy(a_cp + b_cp)
        if _ADD_KERNEL is not None:
            out = cp.empty_like(a_cp)
            n = a_cp.size
            grid = (n // 256 + 1,)
            _ADD_KERNEL(grid, (256,), (a_cp, b_cp, out, n))
            result = cp.asnumpy(out)
        return result.tolist()
    if _rust_add:
        return _rust_add(a, b)
    # Python fallback
    _emit_gpu_performance_warning("elementwise addition", "5-20x slower")
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def elementwise_mul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Multiply matrices *a* and *b* elementwise using CUDA when available."""

    if USE_GPU and cp:
        a_cp = cp.array(a)
        b_cp = cp.array(b)
        result = cp.asnumpy(a_cp * b_cp)
        if _MUL_KERNEL is not None:
            out = cp.empty_like(a_cp)
            n = a_cp.size
            grid = (n // 256 + 1,)
            _MUL_KERNEL(grid, (256,), (a_cp, b_cp, out, n))
            result = cp.asnumpy(out)
        return result.tolist()
    if _rust_mul:
        return _rust_mul(a, b)
    # Python fallback
    _emit_gpu_performance_warning("elementwise multiplication", "5-20x slower")
    return [[a[i][j] * b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Matrix multiply using CUDA when available."""

    if USE_GPU and cp:
        a_cp = cp.array(a)
        b_cp = cp.array(b)
        result = cp.asnumpy(a_cp @ b_cp)
        return result.tolist()
    if _rust_matmul:
        return _rust_matmul(a, b)
    # Python fallback
    _emit_gpu_performance_warning("matrix multiplication", "10-100x slower")
    if not a or not b or len(a[0]) != len(b):
        raise ValueError("Incompatible matrices")
    cols = len(b[0])
    result = [[0.0 for _ in range(cols)] for _ in range(len(a))]
    for i, row in enumerate(a):
        for k, val in enumerate(row):
            for j in range(cols):
                result[i][j] += val * b[k][j]
    return result


def conv2d(input_: List[List[float]], kernel: List[List[float]]) -> List[List[float]]:
    """2D convolution using CUDA when available."""

    if USE_GPU and cp and cpsignal:
        inp = cp.array(input_)
        ker = cp.array(kernel)
        res = cpsignal.convolve2d(inp, ker, mode="valid")
        return cp.asnumpy(res).tolist()
    if _rust_conv2d:
        return _rust_conv2d(input_, kernel)
    # Python fallback
    _emit_gpu_performance_warning("2D convolution", "50-500x slower")
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


def benchmark_elementwise_mul(
    a: List[List[float]], b: List[List[float]], repeat: int = 3
) -> dict[str, float]:
    """Return average CPU and GPU times in ms for elementwise multiplication."""

    start = time.perf_counter()
    for _ in range(repeat):
        if _rust_mul:
            _rust_mul(a, b)
        else:
            elementwise_mul(a, b)
    cpu = (time.perf_counter() - start) * 1e3 / repeat
    if USE_GPU and cp:
        start = time.perf_counter()
        for _ in range(repeat):
            elementwise_mul(a, b)
        gpu = (time.perf_counter() - start) * 1e3 / repeat
    else:
        gpu = float("inf")
    return {"cpu_ms": cpu, "gpu_ms": gpu}


def benchmark_matmul(
    a: List[List[float]], b: List[List[float]], repeat: int = 3
) -> dict[str, float]:
    """Return average CPU and GPU times in ms for matrix multiplication."""

    start = time.perf_counter()
    for _ in range(repeat):
        if _rust_matmul:
            _rust_matmul(a, b)
        else:
            matmul(a, b)
    cpu = (time.perf_counter() - start) * 1e3 / repeat
    if USE_GPU and cp:
        start = time.perf_counter()
        for _ in range(repeat):
            matmul(a, b)
        gpu = (time.perf_counter() - start) * 1e3 / repeat
    else:
        gpu = float("inf")
    return {"cpu_ms": cpu, "gpu_ms": gpu}


def benchmark_conv2d(
    a: List[List[float]], k: List[List[float]], repeat: int = 3
) -> dict[str, float]:
    """Return average CPU and GPU times in ms for 2D convolution."""

    start = time.perf_counter()
    for _ in range(repeat):
        if _rust_conv2d:
            _rust_conv2d(a, k)
        else:
            conv2d(a, k)
    cpu = (time.perf_counter() - start) * 1e3 / repeat
    if USE_GPU and cp and cpsignal:
        start = time.perf_counter()
        for _ in range(repeat):
            conv2d(a, k)
        gpu = (time.perf_counter() - start) * 1e3 / repeat
    else:
        gpu = float("inf")
    return {"cpu_ms": cpu, "gpu_ms": gpu}


def benchmark_tensor_ops(
    a: List[List[float]], b: List[List[float]], k: List[List[float]], repeat: int = 3
) -> dict[str, dict[str, float]]:
    """Benchmark tensor ops across CPU and GPU."""

    return {
        "elementwise_mul": benchmark_elementwise_mul(a, b, repeat),
        "matmul": benchmark_matmul(a, b, repeat),
        "conv2d": benchmark_conv2d(a, k, repeat),
    }


def set_device(device_id: int) -> None:
    """Select active GPU device."""

    global GPU_DEVICE  # noqa: PLW0603 - Global state required for GPU device management
    GPU_DEVICE = device_id
    if cp and USE_GPU:
        cp.cuda.Device(device_id).use()


__all__ = [
    "USE_GPU",
    "GPU_DEVICE",
    "elementwise_add",
    "elementwise_mul",
    "matmul",
    "conv2d",
    "benchmark_elementwise_mul",
    "benchmark_matmul",
    "benchmark_conv2d",
    "benchmark_tensor_ops",
    "set_device",
]
