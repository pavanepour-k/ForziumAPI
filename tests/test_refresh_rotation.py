# flake8: noqa
import importlib


def test_refresh_token_rotation(tmp_path, monkeypatch):
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(tmp_path / "rbac.db"))
    import forzium.security as security

    importlib.reload(security)

    payload = {"user": "alice", "scopes": ["refresh"]}
    refresh = security.create_jwt(payload, "refresh")

    result = security.refresh_and_rotate(refresh, "access", "refresh")
    assert result is not None
    new_access, new_refresh = result

    assert security.is_token_revoked(refresh)
    log_actions = [entry["action"] for entry in security.get_audit_log()]
    assert {"revoked", "rotated", "refreshed"}.issubset(set(log_actions))
    decoded_access = security.decode_jwt(new_access, "access")
    assert isinstance(decoded_access, dict) and decoded_access.get("user") == "alice"
    decoded_refresh = security.decode_jwt(new_refresh, "refresh")
    assert isinstance(decoded_refresh, dict) and decoded_refresh.get("user") == "alice"