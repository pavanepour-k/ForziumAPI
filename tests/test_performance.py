import asyncio
import time
import tracemalloc
import httpx
import forzium_engine
from forzium_engine import ForziumHttpServer, ComputeRequestSchema


def start_server(port: int) -> ForziumHttpServer:
    server = ForziumHttpServer()
    server.serve(f"127.0.0.1:{port}")
    time.sleep(0.2)
    return server


async def _hit_health(port: int, count: int):
    async with httpx.AsyncClient() as client:
        tasks = [client.get(f"http://127.0.0.1:{port}/health") for _ in range(count)]
        start = time.perf_counter()
        responses = await asyncio.gather(*tasks)
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
        assert peak - current < 5_000_000
    finally:
        server.shutdown()


def test_ffi_overhead_validation():
    schema = ComputeRequestSchema()
    payload = {"data": [[1.0]], "operation": "add", "parameters": {"addend": 1.0}}
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        schema.validate(payload)
    avg = (time.perf_counter() - start) / iterations
    assert avg < 0.001


def _py_matmul(a, b):
    return [[sum(x * y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


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
    assert rust_time < py_time