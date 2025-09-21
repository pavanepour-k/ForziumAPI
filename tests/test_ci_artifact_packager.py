from __future__ import annotations

import json
from pathlib import Path

from scripts.prepare_ci_artifacts import collect_ci_artifacts


def test_collect_ci_artifacts_copies_expected_files(tmp_path: Path) -> None:
    base = tmp_path / "repo"
    (base / "metrics").mkdir(parents=True)
    (base / "metrics" / "metric.json").write_text("{}", encoding="utf-8")

    gating = base / "gating.yaml"
    gating.write_text("version: 1", encoding="utf-8")

    dashboards = base / "infrastructure/monitoring/dashboards"
    dashboards.mkdir(parents=True)
    (dashboards / "dash.json").write_text('{"dashboard": {"title": "demo"}}', encoding="utf-8")

    captures = base / "infrastructure/monitoring/captures"
    captures.mkdir(parents=True)
    (captures / "capture.png").write_bytes(b"PNG")

    tests_artifacts = base / "tests/.artifacts"
    tests_artifacts.mkdir(parents=True)
    (tests_artifacts / "diff.txt").write_text("diff", encoding="utf-8")

    output = tmp_path / "out"
    manifest = collect_ci_artifacts(base, output, retention_days=14)

    packaged = {entry["destination"] for entry in manifest["artifacts"]}
    assert "metrics/metric.json" in packaged
    assert "policy/gating.yaml" in packaged
    assert "dashboards/json/dash.json" in packaged
    assert "dashboards/captures/capture.png" in packaged
    assert "tests/artifacts/diff.txt" in packaged
    assert manifest["retention_days"] == 14

    reloaded = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert reloaded == manifest
    assert (output / "RETENTION.txt").read_text(encoding="utf-8").startswith(
        "Forzium CI artifact bundle."
    )


def test_repository_dashboards_are_packaged(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output = tmp_path / "ci"
    manifest = collect_ci_artifacts(repo_root, output)

    sources = {entry["source"] for entry in manifest["artifacts"]}
    assert any(
        src.startswith("infrastructure/monitoring/dashboards/") for src in sources
    ), "Grafana dashboards were not packaged"
    assert any(
        src.startswith("infrastructure/monitoring/captures/") for src in sources
    ), "Dashboard captures were not packaged"
    assert (output / "dashboards/json").exists()
    assert (output / "dashboards/captures").exists()