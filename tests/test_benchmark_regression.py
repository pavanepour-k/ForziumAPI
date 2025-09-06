"""Ensure benchmark metrics do not regress against baseline."""

import pytest

from scripts.benchmark_regression import check_regression, load_baseline
from scripts.run_benchmarks import run_benchmark

pytest.importorskip("forzium_engine")
from tests.test_performance import start_server  # noqa: E402


def test_benchmark_regression() -> None:
    server = start_server(8070)
    try:
        baseline = load_baseline("_docs/benchmark_baseline.json")
        metrics = run_benchmark(duration=1, concurrency=1)
        assert check_regression(baseline, metrics)
    finally:
        server.shutdown()  # type: ignore[attr-defined]