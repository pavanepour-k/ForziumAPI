"""Ensure all test files end with a newline."""

import os
import pathlib


def test_files_end_with_newline() -> None:
    repo_root = pathlib.Path(__file__).parent
    checked = [
        repo_root / "test_api.py",
        repo_root / "test_integration_server.py",
        repo_root / "test_path_params.py",
        repo_root / "test_performance.py",
        repo_root / "test_rust_routes.py",
        repo_root / "test_rust_server.py",
        pathlib.Path(__file__),
    ]
    for path in checked:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            assert f.read(1) == b"\n", f"{path} missing newline at EOF"
