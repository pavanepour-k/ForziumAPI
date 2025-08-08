"""Test the Forzium CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_cli_scaffold_and_commands(tmp_path) -> None:
    proj = tmp_path / "demo"
    subprocess.run([sys.executable, "-m", "forzium.cli", "new", str(proj)], check=True)
    assert (proj / "app.py").exists()
    assert (proj / ".pre-commit-config.yaml").exists()

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
    result = subprocess.run(
        [sys.executable, "-m", "forzium.cli", "bench", "--size", "2"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "conv2d" in data
