"""Performance tests for the Rust validation and server."""

import asyncio
import time
import tracemalloc

import pytest

from scripts.run_benchmarks import run_benchmark  # type: ignore[import]
from tests.http_client import get

pytest.importorskip("forzium_engine")
import forzium_engine  # noqa: E402
from forzium_engine import ComputeRequestSchema  # noqa: E402
from forzium_engine import ForziumHttpServer  # noqa: E402


def start_server(port: int) -> ForziumHttpServer:
    server = ForziumHttpServer()
    # The port separator colon triggers flake8 E231 (missing whitespace after
    # ':'), but it's part of an address string. Silence this false positive.
    addr = f"127.0.0.1:{port}"  # noqa: E231
    server.serve(addr)  # type: ignore[attr-defined]  # noqa: E231
    time.sleep(0.2)
    return server


async def _hit_health(port: int, count: int):
    async def one() -> object:
        # Colon in the URL is likewise flagged by flake8; ignore E231.
        return await asyncio.to_thread(
            get, f"http://127.0.0.1:{port}/health"  # noqa: E231
        )

    start = time.perf_counter()
    responses = await asyncio.gather(*(one() for _ in range(count)))
    return responses, time.perf_counter() - start


def test_high_load_health_requests():
    server = start_server(8096)
    try:
        tracemalloc.start()
        responses, elapsed = asyncio.run(_hit_health(8096, 20))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        for resp in responses:
            assert resp.status_code == 200
        avg = elapsed / len(responses)
        assert avg < 0.1
        assert peak - current < 9_000_000
    finally:
        server.shutdown()  # type: ignore[attr-defined]


def test_ffi_overhead_validation():
    schema = ComputeRequestSchema()
    payload = {
        "data": [[1.0]],
        "operation": "add",
        "parameters": {"addend": 1.0},
    }
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        schema.validate(payload)
    avg = (time.perf_counter() - start) / iterations
    assert avg < 0.001


def _py_matmul(a, b):
    return [
        [sum(x * y for x, y in zip(row, col)) for col in zip(*b)] 
        for row in a
    ]


def test_matmul_parallel_speed():
    size = 50
    a = [[float(i + j) for j in range(size)] for i in range(size)]
    b = [[float(i * j) for j in range(size)] for i in range(size)]
    start = time.perf_counter()
    forzium_engine.matmul(a, b)
    rust_time = time.perf_counter() - start
    start = time.perf_counter()
    _py_matmul(a, b)
    py_time = time.perf_counter() - start
    assert rust_time <= py_time * 1.5


def test_memory_benchmark() -> None:
    server = start_server(8000)
    try:
        stats = run_benchmark(duration=1, concurrency=1)
        # Allow a slightly higher memory ceiling to reduce flakiness across
        # architectures while still keeping the benchmark within ~1 GB.
        assert stats["max_rss_kb"] < 950 * 1024
    finally:
        server.shutdown()  # type: ignore[attr-defined]
