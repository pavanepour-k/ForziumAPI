"""Ensure NUMA pool benchmarking returns timings for each node."""

from scripts.benchmark_numa import benchmark_numa


def test_benchmark_numa() -> None:
    timings = benchmark_numa(1024, 2, iters=10)
    assert set(timings.keys()) == {0, 1}
    for t in timings.values():
        assert t >= 0
