"""Ensure benchmark metrics comply with the regression gate policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.benchmark_regression import metrics_to_report
from scripts.performance_gate import (
    RegressionPolicy,
    evaluate_policy,
    load_metrics_report,
)
from scripts.run_benchmarks import run_benchmark

pytest.importorskip("forzium_engine")
from tests.test_performance import start_server  # noqa: E402


def _write_policy(tmp_path: Path) -> tuple[Path, Path]:
    baseline_path = tmp_path / "baseline.json"
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
version: 1
baseline_reference: baseline.json
metrics:
  throughput_rps:
    source: aggregate.throughput_rps.mean
    comparison: greater_or_equal
    tolerance: 0.50
  latency_p95_ms:
    source: aggregate.latency_p95_ms
    comparison: less_or_equal
    tolerance: 0.50
  error_rate:
    source: aggregate.error_rate_total
    comparison: less_or_equal
    tolerance: 0.0
""",
        encoding="utf-8",
    )
    return policy_path, baseline_path


def test_benchmark_regression(tmp_path: Path) -> None:
    server = start_server(8070)
    try:
        metrics = run_benchmark(duration=1, concurrency=1)
        report = metrics_to_report(metrics, duration=1, concurrency=1)

        policy_path, baseline_path = _write_policy(tmp_path)
        baseline_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        policy = RegressionPolicy.load(policy_path)
        baseline_report = load_metrics_report(baseline_path)
        outcome = evaluate_policy(policy, baseline_report, report)
        assert outcome.passed
    finally:
        server.shutdown()  # type: ignore[attr-defined]