from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.release_gate import (
    CommandGateDefinition,
    GateDefinition,
    GateResult,
    JsonGateDefinition,
    JsonRequirement,
    RegressionGateDefinition,
    evaluate_command_gate,
    evaluate_json_gate,
    evaluate_regression_gate,
    load_checklist,
    run_checklist,
)


def test_load_checklist_parses_repository_file() -> None:
    """The committed checklist must be loadable without errors."""

    checklist_path = Path(__file__).resolve().parents[1] / "docs" / "release_checklist.yaml"
    gates = load_checklist(checklist_path)
    gate_ids = {gate.gate_id for gate in gates}
    assert {"functional", "compatibility", "regression", "stability", "observability_metrics"}.issubset(
        gate_ids
    )


def test_evaluate_command_gate_success(tmp_path: Path) -> None:
    """A passing command should mark the gate as successful."""

    script = tmp_path / "echo.py"
    script.write_text("print('ok')", encoding="utf-8")
    gate = CommandGateDefinition(
        gate_id="cmd",
        description="echo",
        command=["python", str(script)],
    )
    result = evaluate_command_gate(gate, tmp_path)
    assert result.passed
    assert "ok" in result.details


def test_evaluate_command_gate_failure(tmp_path: Path) -> None:
    """Failing commands should report stderr output."""

    gate = CommandGateDefinition(
        gate_id="cmd",
        description="boom",
        command=["python", "-c", "import sys; sys.exit(3)"],
    )
    result = evaluate_command_gate(gate, tmp_path)
    assert not result.passed
    assert "no output" in result.details.lower()


@pytest.fixture()
def regression_paths(tmp_path: Path) -> tuple[RegressionGateDefinition, Path]:
    """Provide a passing regression configuration in a temp directory."""

    policy = tmp_path / "gating.yaml"
    policy.write_text(
        """
version: 1
baseline_reference: baseline.json
metrics:
  throughput:
    source: aggregate.throughput
    comparison: greater_or_equal
    tolerance: 0.05
""",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"aggregate": {"throughput": 200.0}}), encoding="utf-8")
    candidate.write_text(json.dumps({"aggregate": {"throughput": 210.0}}), encoding="utf-8")
    gate = RegressionGateDefinition(
        gate_id="reg",
        description="regression",
        policy=policy,
        baseline=baseline,
        candidate=candidate,
    )
    return gate, tmp_path


def test_evaluate_regression_gate_passes(regression_paths: tuple[RegressionGateDefinition, Path]) -> None:
    """Regression gate passes when metrics meet policy."""

    gate, base_path = regression_paths
    result = evaluate_regression_gate(gate, base_path)
    assert result.passed
    assert "throughput" in result.details


def test_evaluate_regression_gate_failure(regression_paths: tuple[RegressionGateDefinition, Path]) -> None:
    """Regression gate fails when metrics violate policy."""

    gate, base_path = regression_paths
    (base_path / "candidate.json").write_text(
        json.dumps({"aggregate": {"throughput": 150.0}}), encoding="utf-8"
    )
    result = evaluate_regression_gate(gate, base_path)
    assert not result.passed
    assert "passed" in result.details.lower() or "error" in result.details.lower()


def test_evaluate_json_gate_constraints(tmp_path: Path) -> None:
    """JSON gates should enforce equals/min/max constraints."""

    payload = tmp_path / "metrics.json"
    payload.write_text(
        json.dumps({"a": {"b": {"value": 2, "flag": True}}}), encoding="utf-8"
    )
    gate = JsonGateDefinition(
        gate_id="json",
        description="json",
        path=payload,
        requirements=[
            JsonRequirement(path="a.b.flag", equals=True),
            JsonRequirement(path="a.b.value", min_value=1.0, max_value=3.0),
        ],
    )
    result = evaluate_json_gate(gate, tmp_path)
    assert result.passed


def test_run_checklist_dispatches() -> None:
    """run_checklist should dispatch to the appropriate evaluators."""

    repo_root = Path.cwd()
    gates: list[GateDefinition] = [
        CommandGateDefinition("cmd", "noop", ["python", "-c", "print('ok')"]),
    ]
    results = run_checklist(gates, repo_root)
    assert len(results) == 1
    assert isinstance(results[0], GateResult)