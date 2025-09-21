"""Unit tests for the regression gating utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.performance_gate import (
    RegressionPolicy,
    evaluate_policy,
    render_html_report,
    save_metrics_report,
)


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    content = """
version: 1
baseline_reference: baseline.json
metrics:
  throughput_rps:
    source: aggregate.throughput_rps.mean
    comparison: greater_or_equal
    tolerance: 0.05
  latency_p95_ms:
    source: aggregate.latency_p95_ms
    comparison: less_or_equal
    tolerance: 0.10
  error_rate_total:
    source: aggregate.error_rate_total
    comparison: less_or_equal
    tolerance: 0.0
metadata:
  generated_by: test-suite
"""
    path = tmp_path / "gating.yaml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def baseline_file(tmp_path: Path) -> Path:
    baseline = {
        "aggregate": {
            "throughput_rps": {"mean": 2000.0},
            "latency_p95_ms": 20.0,
            "error_rate_total": 0.0,
        }
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return path


def test_gate_failure_detected(policy_file: Path, baseline_file: Path) -> None:
    policy = RegressionPolicy.load(policy_file)
    baseline_report = json.loads(baseline_file.read_text(encoding="utf-8"))
    current_report = {
        "aggregate": {
            "throughput_rps": {"mean": 1800.0},
            "latency_p95_ms": 25.0,
            "error_rate_total": 0.02,
        }
    }

    outcome = evaluate_policy(policy, baseline_report, current_report)
    assert not outcome.passed

    report_path = baseline_file.parent / "report.html"
    render_html_report(outcome, report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "FAIL" in html


def test_save_metrics_report(policy_file: Path, tmp_path: Path) -> None:
    policy = RegressionPolicy.load(policy_file)
    baseline_report = {
        "aggregate": {
            "throughput_rps": {"mean": 2000.0},
            "latency_p95_ms": 20.0,
            "error_rate_total": 0.0,
        }
    }
    outcome = evaluate_policy(policy, baseline_report, baseline_report)
    assert outcome.passed

    metrics_path = tmp_path / "artifact.json"
    save_metrics_report(baseline_report, metrics_path)
    saved = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert saved["aggregate"]["throughput_rps"]["mean"] == 2000.0