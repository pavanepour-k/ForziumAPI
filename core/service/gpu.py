"""Optional GPU-accelerated tensor helpers.

This module uses CuPy when available and enabled via the
``FORZIUM_USE_GPU`` environment variable. Operations fall back to a
Rust-powered CPU implementation otherwise. A GPU device may be selected
via ``FORZIUM_GPU_DEVICE``.
"""

from __future__ import annotations

import os
from typing import List
import time

from forzium_engine import (
    conv2d as _rust_conv2d,
    elementwise_add as _rust_add,
    elementwise_mul as _rust_mul,
    simd_matmul as _rust_matmul,
)

try:  # pragma: no cover - optional dependency
    import cupy as cp  # type: ignore
except Exception:  # pragma: no cover
    cp = None  # type: ignore
try:  # pragma: no cover - optional dependency
    import cupyx.scipy.signal as cpsignal  # type: ignore
except Exception:  # pragma: no cover
    cpsignal = None  # type: ignore

GPU_DEVICE = int(os.getenv("FORZIUM_GPU_DEVICE", "0"))
USE_GPU = bool(cp) and os.getenv("FORZIUM_USE_GPU") == "1"
if USE_GPU and cp and hasattr(cp, "cuda"):
    try:  # pragma: no cover - optional dependency
        cp.cuda.Device(GPU_DEVICE).use()
    except Exception:  # pragma: no cover
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
    return _rust_add(a, b)


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
    return _rust_mul(a, b)


def matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Matrix multiply using CUDA when available."""

    if USE_GPU and cp:
        a_cp = cp.array(a)
        b_cp = cp.array(b)
        result = cp.asnumpy(a_cp @ b_cp)
        return result.tolist()
    return _rust_matmul(a, b)


def conv2d(input_: List[List[float]], kernel: List[List[float]]) -> List[List[float]]:
    """2D convolution using CUDA when available."""

    if USE_GPU and cp and cpsignal:
        inp = cp.array(input_)
        ker = cp.array(kernel)
        res = cpsignal.convolve2d(inp, ker, mode="valid")
        return cp.asnumpy(res).tolist()
    return _rust_conv2d(input_, kernel)


def benchmark_elementwise_mul(
    a: List[List[float]], b: List[List[float]], repeat: int = 3
) -> dict[str, float]:
    """Return average CPU and GPU times in ms for elementwise multiplication."""

    start = time.perf_counter()
    for _ in range(repeat):
        _rust_mul(a, b)
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
        _rust_matmul(a, b)
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
        _rust_conv2d(a, k)
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

    global GPU_DEVICE, USE_GPU
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
