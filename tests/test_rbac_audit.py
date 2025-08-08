import importlib
import sqlite3

from forzium import security


def test_rbac_and_audit_log(monkeypatch, tmp_path) -> None:
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    importlib.reload(security)

    security.define_role("admin", ["read", "write"])
    security.assign_role("alice", "admin")
    assert security.check_permission("alice", "write")
    assert not security.check_permission("alice", "delete")

    token = security.create_jwt({"user": "alice"}, "s")
    security.revoke_token(token)
    events = [e["action"] for e in security.get_audit_log()]
    assert "created" in events and "revoked" in events

    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM roles")
        assert cur.fetchone()[0] == "admin"


def test_rbac_crud(monkeypatch, tmp_path) -> None:
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    importlib.reload(security)

    security.define_role("user", ["read"])
    security.assign_role("bob", "user")
    assert security.list_roles() == ["user"]
    assert security.list_user_roles("bob") == ["user"]
    security.remove_role("bob", "user")
    assert security.list_user_roles("bob") == []
