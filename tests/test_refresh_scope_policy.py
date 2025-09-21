import importlib


def test_refresh_requires_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security
    importlib.reload(security)

    payload = {"user": "bob"}
    refresh = security.create_jwt(payload, "r")
    assert security.refresh_jwt(refresh, "a", "r") is None
    scoped = security.create_jwt({"user": "bob", "scopes": ["refresh"]}, "r")
    assert security.refresh_jwt(scoped, "a", "r") is not None