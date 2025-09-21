from __future__ import annotations

import json
from pathlib import Path

import pytest

from infrastructure.monitoring.soak import (
    SoakAnalyzer,
    SoakConfig,
    SoakRun,
    SoakSample,
    evaluate_soak_file,
    iter_reports,
    load_soak_run,
)


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "metrics" / name


def test_reference_soak_dataset_passes_budget() -> None:
    path = _fixture_path("soak_reference_timeseries.json")
    run, config = load_soak_run(path)
    report = SoakAnalyzer(config).evaluate(run)
    assert report.passed
    assert report.duration_hours >= config.min_duration_hours
    assert report.span_closure_ratio == pytest.approx(1.0)
    assert report.container_restarts == 0
    assert report.rss_drift_bytes <= config.rss_drift_budget_bytes
    assert not report.violations


def test_evaluate_soak_file_helper_matches_manual_run() -> None:
    path = _fixture_path("soak_reference_timeseries.json")
    direct_report = evaluate_soak_file(path)
    run, config = load_soak_run(path)
    analyzer_report = SoakAnalyzer(config).evaluate(run)
    assert direct_report.to_gate_payload() == analyzer_report.to_gate_payload()


def test_soak_report_flags_violations_for_restart_and_span_leak() -> None:
    baseline = SoakSample.from_dict(
        {
            "timestamp": "2025-09-19T00:00:00Z",
            "rss_bytes": 500,
            "container_restarts": 0,
            "spans_started": 100,
            "spans_closed": 100,
        }
    )
    later = SoakSample.from_dict(
        {
            "timestamp": "2025-09-19T01:30:00Z",
            "rss_bytes": 1200,
            "container_restarts": 2,
            "spans_started": 300,
            "spans_closed": 298,
        }
    )
    run = SoakRun(metadata={}, samples=[baseline, later])
    config = SoakConfig(
        min_duration_hours=2.0,
        rss_drift_budget_bytes=200,
        max_container_restarts=1,
    )
    report = SoakAnalyzer(config).evaluate(run)
    assert not report.passed
    assert report.span_deficit == 2
    assert report.container_restarts == 2
    assert report.rss_drift_bytes == 700
    assert any("container restarts" in message for message in report.violations)
    assert any("spans missing" in message for message in report.violations)
    assert any("rss drift" in message for message in report.violations)
    assert any("duration" in message for message in report.violations)


def test_iter_reports_handles_multiple_inputs(tmp_path: Path) -> None:
    payload = json.loads(_fixture_path("soak_reference_timeseries.json").read_text(encoding="utf-8"))
    alt_path = tmp_path / "alt.json"
    with alt_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    reports = iter_reports([
        _fixture_path("soak_reference_timeseries.json"),
        alt_path,
    ])
    assert len(reports) == 2
    assert all(report.passed for report in reports)