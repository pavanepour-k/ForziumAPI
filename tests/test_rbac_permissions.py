# flake8: noqa
import importlib
import time

from forzium import ForziumApp
from forzium.middleware import JWTAuthMiddleware
from forzium.testclient import TestClient


def test_rbac_permission_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security

    importlib.reload(security)

    security.define_role("viewer", ["view"])
    security.assign_role("alice", "viewer")

    app = ForziumApp()
    app.add_middleware(
        JWTAuthMiddleware, secret="secret", permissions=["view"]
    )

    @app.get("/secure")
    def secure():
        return {"ok": True}

    client = TestClient(app)

    token = security.create_jwt({"user": "alice"}, "secret")
    assert client.get("/secure", params={"token": token}).status_code == 200

    bad = security.create_jwt({"user": "bob"}, "secret")
    assert client.get("/secure", params={"token": bad}).status_code == 403
    alice_events = [e["action"] for e in security.get_audit_log("alice")]
    assert "authorized" in alice_events
    bob_events = [e["action"] for e in security.get_audit_log("bob")]
    assert "forbidden" in bob_events


def test_permission_revocation_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security
    import importlib

    importlib.reload(security)
    import forzium.rbac_api as rbac_api
    importlib.reload(rbac_api)

    security.define_role("editor", ["edit"])
    security.assign_role("alice", "editor")

    token = security.create_jwt({"scopes": ["rbac"]}, "secret")
    client = TestClient(rbac_api.router)

    assert security.check_permission("alice", "edit")

    resp = client.request(
        "DELETE",
        "/permissions",
        json_body={"role": "editor", "permission": "edit"},
        params={"token": token},
    )
    assert resp.status_code == 200
    assert not security.check_permission("alice", "edit")


def test_permission_any_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security

    importlib.reload(security)

    security.define_role("writer", ["write"])
    security.assign_role("carol", "writer")

    app = ForziumApp()
    app.add_middleware(
        JWTAuthMiddleware,
        secret="secret",
        permissions=["read", "write"],
        permission_mode="any",
    )

    @app.get("/any")
    def secure_any():
        return {"ok": True}

    client = TestClient(app)

    token = security.create_jwt({"user": "carol"}, "secret")
    assert client.get("/any", params={"token": token}).status_code == 200

    bad = security.create_jwt({"user": "dave"}, "secret")
    assert client.get("/any", params={"token": bad}).status_code == 403


def test_permission_all_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security

    importlib.reload(security)

    security.define_role("editor", ["read", "write"])
    security.assign_role("erin", "editor")
    security.define_role("reader", ["read"])
    security.assign_role("frank", "reader")

    app = ForziumApp()
    app.add_middleware(
        JWTAuthMiddleware,
        secret="secret",
        permissions=["read", "write"],
        permission_mode="all",
    )

    @app.get("/all")
    def secure_all():
        return {"ok": True}

    client = TestClient(app)

    good = security.create_jwt({"user": "erin"}, "secret")
    assert client.get("/all", params={"token": good}).status_code == 200

    bad = security.create_jwt({"user": "frank"}, "secret")
    assert client.get("/all", params={"token": bad}).status_code == 403


def test_hierarchical_and_expiring_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security

    importlib.reload(security)

    # hierarchical permission via wildcard
    security.define_role("admin", ["resource:*"])
    security.assign_role("harry", "admin")

    # time-bound permission
    future = time.time() + 10
    past = time.time() - 10
    security.define_role("temp", [("temp", future)])
    security.define_role("expired", [("temp", past)])
    security.assign_role("ivy", "temp")
    security.assign_role("jane", "expired")

    app = ForziumApp()
    app.add_middleware(
        JWTAuthMiddleware,
        secret="secret",
        permissions=["resource:delete", "temp"],
        permission_mode="any",
    )

    @app.get("/test")
    def secure():
        return {"ok": True}

    client = TestClient(app)

    admin_token = security.create_jwt({"user": "harry"}, "secret")
    assert client.get("/test", params={"token": admin_token}).status_code == 200

    good = security.create_jwt({"user": "ivy"}, "secret")
    assert client.get("/test", params={"token": good}).status_code == 200

    bad = security.create_jwt({"user": "jane"}, "secret")
    assert client.get("/test", params={"token": bad}).status_code == 403


def test_permission_cache_purges_expired(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security

    importlib.reload(security)

    now = time.time()
    security.define_role("temp", [("perm", now + 1)])
    security.assign_role("user", "temp")

    assert security.check_permission("user", "perm")

    monkeypatch.setattr(security.time, "time", lambda: now + 2)
    assert not security.check_permission("user", "perm")

    with security._conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM role_permissions WHERE perm='perm'")
        assert cur.fetchone()[0] == 0