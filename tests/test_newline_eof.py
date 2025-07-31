import os
import pathlib


def test_files_end_with_newline():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    for path in repo_root.rglob('*.py'):
        with open(path, 'rb') as f:
            f.seek(-1, os.SEEK_END)
            assert f.read(1) == b'\n', f"{path} missing newline at EOF"