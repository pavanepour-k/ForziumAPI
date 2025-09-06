import os
import sqlite3
import subprocess
import sys

import infrastructure.monitoring.otlp_exporter as exporter
from forzium import cli


def test_migrate_script(tmp_path) -> None:
    db = tmp_path / "rbac.db"
    env = os.environ.copy()
    env["FORZIUM_RBAC_DB"] = str(db)
    subprocess.run([sys.executable, "scripts/migrate_rbac.py"], check=True, env=env)
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    assert {"roles", "role_permissions", "user_roles", "audit_log"} <= tables


def test_cli_replay_otlp(tmp_path, monkeypatch) -> None:
    fail_dir = tmp_path / "buf"
    fail_dir.mkdir()
    (fail_dir / "1.json").write_text("[]")

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(exporter.request, "urlopen", lambda *a, **k: Resp())
    cli.main(["replay-otlp", str(fail_dir), "http://example"])
    assert not list(fail_dir.glob("*.json"))
