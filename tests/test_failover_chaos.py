from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from infrastructure.monitoring.failover import (
    ChaosEvent,
    ComponentRecovery,
    FailoverAnalyzer,
    FailoverConfig,
    FailoverReport,
    FailoverRun,
    ResourceSnapshot,
    evaluate_failover_file,
    load_failover_run,
)


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "metrics" / name


def test_reference_failover_dataset_passes() -> None:
    path = _fixture_path("chaos_failover_reference.json")
    run, config = load_failover_run(path)
    report = FailoverAnalyzer(config).evaluate(run)
    assert report.passed
    assert report.recovered
    assert report.leak_count == 0
    assert report.stability_confirmed
    assert pytest.approx(8.0, rel=1e-6) == report.max_recovery_seconds
    assert len(report.component_results) == 3
    assert all(isinstance(item, ComponentRecovery) for item in report.component_results)


def test_evaluate_failover_file_helper_matches_manual() -> None:
    path = _fixture_path("chaos_failover_reference.json")
    direct_report = evaluate_failover_file(path)
    run, config = load_failover_run(path)
    analyzer_report = FailoverAnalyzer(config).evaluate(run)
    assert isinstance(direct_report, FailoverReport)
    assert direct_report.to_gate_payload() == analyzer_report.to_gate_payload()


def test_failover_report_flags_unrecovered_and_leaks() -> None:
    failure_time = datetime(2025, 9, 20, 10, 0, 0, tzinfo=timezone.utc)
    run = FailoverRun(
        metadata={"scenario": "failure-case"},
        events=[
            ChaosEvent(
                timestamp=failure_time,
                component="worker:ingest-1",
                kind="failure",
                metadata={"signal": "SIGKILL"},
            ),
            ChaosEvent(
                timestamp=failure_time.replace(second=5),
                component="network",
                kind="failure",
                metadata={"profile": "tc-loss"},
            ),
            ChaosEvent(
                timestamp=failure_time.replace(second=8),
                component="network",
                kind="recovery",
                metadata={"profile": "clear"},
            ),
            ChaosEvent(
                timestamp=failure_time.replace(second=15),
                component="cluster",
                kind="stability",
                metadata={"window_seconds": 10},
            ),
        ],
        resources=[
            ResourceSnapshot(name="open_fds", baseline=200, post_recovery=212),
            ResourceSnapshot(name="background_tasks", baseline=4, post_recovery=5),
        ],
    )
    config = FailoverConfig(
        max_recovery_seconds=6.0,
        stability_window_seconds=20.0,
        resource_tolerances={"open_fds": 0, "background_tasks": 1},
    )
    report = FailoverAnalyzer(config).evaluate(run)
    assert not report.passed
    assert not report.recovered
    assert report.leak_count == 1
    assert any("open_fds" in entry for entry in report.violations)
    assert any("stability window" in entry for entry in report.violations)