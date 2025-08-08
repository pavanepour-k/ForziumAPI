"""Tests for memory pool profiling."""

from core.service.orchestration_service import profile_pool


class DummyPool:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.used = 0

    def allocate(self, size: int) -> bytearray:
        self.used += size
        return bytearray(size)

    def deallocate(self, block: bytearray) -> None:
        self.used -= len(block)

    def available(self) -> int:
        return self.capacity - self.used


def test_profile_pool() -> None:
    pool = DummyPool(1024)
    peak = profile_pool(pool, 4, 100)
    assert peak >= 100
