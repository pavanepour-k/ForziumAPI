"""Tests for memory management bindings."""

from core.service import orchestration_service as svc, orchestration_service
import tracemalloc


def test_force_gc_exists():
    assert hasattr(svc.forzium_engine, "force_gc")
    svc.forzium_engine.force_gc()


def test_pool_allocator_zero_copy() -> None:
    pool = orchestration_service.PoolAllocator(64)
    block = pool.allocate(16)
    view = memoryview(block)
    view[0] = 1
    pool.deallocate(block)
    assert pool.available() == 64


def test_zero_copy_multiply() -> None:
    pool = orchestration_service.PoolAllocator(256)
    view = svc.zero_copy_multiply([[1.0, 2.0], [3.0, 4.0]], 2.0, pool)
    assert list(view) == [2.0, 4.0, 6.0, 8.0]


def test_allocator_benchmark_under_limit() -> None:
    pool = orchestration_service.PoolAllocator(600_000_000)
    tracemalloc.start()
    blocks = [pool.allocate(1_000_000) for _ in range(400)]
    current, peak = tracemalloc.get_traced_memory()
    assert peak < 500 * 1024 * 1024
    for blk in blocks:
        pool.deallocate(blk)
    tracemalloc.stop()
