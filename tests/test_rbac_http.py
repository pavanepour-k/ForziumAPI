import importlib
from typing import Dict

from forzium import security
from forzium.app import ForziumApp
from forzium.testclient import TestClient


def test_rbac_http_api(tmp_path, monkeypatch) -> None:
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    monkeypatch.setenv("FORZIUM_SECRET", "s")
    import forzium.rbac_api as rbac_api

    importlib.reload(security)
    importlib.reload(rbac_api)
    app = ForziumApp()
    app.include_router(rbac_api.router, prefix="/rbac")
    client = TestClient(app)
    token = security.create_jwt({"user": "bob", "scopes": ["rbac"]}, "s")
    params: Dict[str, str] = {"token": token}

    client.post(
        "/rbac/roles",
        json_body={"name": "admin", "permissions": ["view"]},
        params=params,
    )
    roles = client.get("/rbac/roles", params=params).json()["roles"]
    assert "admin" in roles
    client.post(
        "/rbac/assign",
        json_body={"user": "alice", "role": "admin"},
        params=params,
    )
    assigned = client.get(
        "/rbac/user-roles", params={"user": "alice", **params}
    ).json()["roles"]
    assert assigned == ["admin"]
    client.request(
        "DELETE",
        "/rbac/assign",
        json_body={"user": "alice", "role": "admin"},
        params=params,
    )
    assigned = client.get(
        "/rbac/user-roles", params={"user": "alice", **params}
    ).json()["roles"]
    assert assigned == []
    client.request(
        "DELETE",
        "/rbac/roles",
        params={"name": "admin", **params},
    )
    roles = client.get("/rbac/roles", params=params).json()["roles"]
    assert roles == []
    log_all = client.get("/rbac/audit-log", params=params).json()["log"]
    log_filtered = client.get(
        "/rbac/audit-log", params={"filter_token": token, **params}
    ).json()["log"]
    assert all(entry["token"] == token for entry in log_filtered)
    assert len(log_filtered) <= len(log_all)

    resp = client.get("/rbac/roles")
    assert resp.status_code == 401
