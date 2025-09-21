from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci_gates import GateManifest, load_manifest


@pytest.fixture(scope="module")
def gating_manifest() -> GateManifest:
    manifest_path = Path(__file__).resolve().parents[1] / "infrastructure" / "ci" / "gates.yaml"
    return load_manifest(manifest_path)


def test_manifest_exposes_all_stages(gating_manifest: GateManifest) -> None:
    stages = gating_manifest.stages
    assert {"L1", "L2", "L3"}.issubset(stages.keys())
    assert gating_manifest.stage("L1").cadence == "per-pr"
    assert gating_manifest.stage("L2").cadence == "daily"
    assert gating_manifest.stage("L3").cadence == "nightly"


def test_l1_contains_unit_snapshot_and_smoke_checks(gating_manifest: GateManifest) -> None:
    stage = gating_manifest.stage("L1")
    commands = {" ".join(check.command) for check in stage.checks}
    assert any("tests/test_api.py" in cmd and "test_dependency_injection.py" in cmd for cmd in commands)
    assert any("tests/test_fastapi_parity.py" in cmd and "tests/test_request_response.py" in cmd for cmd in commands)
    assert any("tests/test_cli_run.py" in cmd for cmd in commands)
    assert stage.expected_runtime_minutes <= 20


def test_l2_covers_load_observability_and_regression(gating_manifest: GateManifest) -> None:
    stage = gating_manifest.stage("L2")
    commands = [check.command for check in stage.checks]
    assert any("scripts/load_suite.py" in cmd for cmd in commands)
    assert any("tests/test_request_observability.py" in cmd for cmd in commands)
    assert any("scripts/benchmark_regression.py" in cmd for cmd in commands)
    assert "metrics/load_suite_report.json" in stage.artifacts
    assert "artifacts/regression_report.html" in stage.artifacts
    assert "artifacts/regression_metrics.json" in stage.artifacts


def test_l3_declares_reports_and_release_gate(gating_manifest: GateManifest) -> None:
    stage = gating_manifest.stage("L3")
    commands = [check.command for check in stage.checks]
    assert any("tests/test_soak_stability.py" in cmd for cmd in commands)
    assert any("tests/test_failover_chaos.py" in cmd for cmd in commands)
    assert any("scripts/prepare_ci_artifacts.py" in cmd for cmd in commands)
    assert any("scripts/release_gate.py" in cmd for cmd in commands)
    expected_artifacts = {
        "metrics/stability_report.json",
        "metrics/soak_reference_timeseries.json",
        "metrics/chaos_failover_reference.json",
        "artifacts/ci/manifest.json",
        "artifacts/ci/RETENTION.txt",
        "artifacts/regression_report.html",
        "artifacts/release_gate.json",
    }
    assert expected_artifacts.issubset(set(stage.artifacts))