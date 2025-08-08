"""Tests for the Rust-backed ComputeEngine"""

import pytest

from core.service.orchestration_service import ENGINE, run_computation

pytestmark = pytest.mark.skipif(ENGINE is None, reason="Rust engine not built")


def test_engine_supports_and_compute() -> None:
    engine = ENGINE
    assert engine.supports("multiply")
    res = engine.compute([[1.0, 2.0]], "multiply", {"factor": 3})
    assert res == [[3.0, 6.0]]


def test_run_computation_integration() -> None:
    out = run_computation([[1.0, 2.0]], "add", {"addend": 1})
    assert out["result"] == [[2.0, 3.0]]


def test_thread_safety() -> None:
    data = [[1.0, 2.0]]
    params = {"factor": 2}
    import concurrent.futures as cf

    with cf.ThreadPoolExecutor(4) as ex:
        futures = [
            ex.submit(ENGINE.compute, data, "multiply", params) for _ in range(4)
        ]
    for f in futures:
        assert f.result() == [[2.0, 4.0]]
