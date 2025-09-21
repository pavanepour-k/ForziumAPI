"""Test the Forzium CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cli_scaffold_and_commands(tmp_path) -> None:
    proj = tmp_path / "demo"
    subprocess.run(
        [sys.executable, "-m", "forzium.cli", "new", str(proj)],
        check=True,
    )
    assert (proj / "app.py").exists()
    assert (proj / "pyproject.toml").exists()
    assert (proj / "README.md").exists()
    assert (proj / ".pre-commit-config.yaml").exists()

    subprocess.run(
        [sys.executable, "-m", "py_compile", str(proj / "app.py"), str(proj / "main.py")],
        check=True,
    )

    env = os.environ | {"FORZIUM_DRYRUN": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "forzium.cli", "build"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert "build_pipeline.py" in result.stdout
    result = subprocess.run(
        [sys.executable, "-m", "forzium.cli", "test"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert "pytest -q" in result.stdout
    result = subprocess.run(
        [sys.executable, "-m", "forzium.cli", "lint"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert "ruff ." in result.stdout
    bench_output = tmp_path / "bench-results.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "forzium.cli",
            "bench",
            "--size",
            "2",
            "--output",
            str(bench_output),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    data = json.loads(result.stdout)
    assert bench_output.exists()
    disk = json.loads(bench_output.read_text())
    assert data == disk
    assert "metrics" in data and set(data["metrics"]) >= {"conv2d", "matmul", "elementwise_mul"}

    runner = tmp_path / "runner"
    runner.mkdir()
    runner_source = "\n".join(
        [
            "from __future__ import annotations",
            "",
            "from pathlib import Path",
            "",
            "",
            "LOG = Path(__file__).with_name(\"run.log\")",
            "",
            "",
            "def record(message: str) -> None:",
            "    LOG.parent.mkdir(parents=True, exist_ok=True)",
            "    with LOG.open(\"a\", encoding=\"utf-8\") as fh:",
            "        fh.write(message + \"\\n\")",
            "",
            "",
            "class DummyServer:",
            "    def serve(self, address: str) -> None:",
            "        record(f\"serve:{address}\")",
            "",
            "    def shutdown(self) -> None:",
            "        record(\"server-shutdown\")",
            "",
            "",
            "class DummyApp:",
            "    def __init__(self, server: DummyServer) -> None:",
            "        self.server = server",
            "",
            "    def startup(self) -> None:",
            "        record(\"startup\")",
            "",
            "    def shutdown(self) -> None:",
            "        record(\"app-shutdown\")",
            "",
            "",
            "server = DummyServer()",
            "app = DummyApp(server)",
            "",
        ]
    )
    (runner / "main.py").write_text(runner_source, encoding="utf-8")

    path_entries = [str(REPO_ROOT), str(runner)]
    existing_path = os.environ.get("PYTHONPATH")
    if existing_path:
        path_entries.append(existing_path)
    run_env = dict(os.environ)
    run_env["PYTHONPATH"] = os.pathsep.join(path_entries)
    run_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "forzium.cli",
            "run",
            "--no-block",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
        ],
        cwd=runner,
        capture_output=True,
        text=True,
        env=run_env,
        check=True,
    )
    log_lines = (runner / "run.log").read_text().splitlines()
    assert "startup" in log_lines
    assert any(line == "serve:127.0.0.1:8123" for line in log_lines)
    assert "Forzium application" in run_result.stdout