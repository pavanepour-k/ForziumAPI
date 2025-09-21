import time
import importlib

import forzium.security as security
from infrastructure import monitoring


def test_distributed_permission_cache_invalidates(tmp_path, monkeypatch):
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    sec = importlib.reload(security)
    sec.define_role("viewer", ["read"])
    sec.assign_role("alice", "viewer")
    assert sec.check_permission("alice", "read")
    assert not sec.check_permission("alice", "write")
    # simulate remote instance updating role permissions
    with sec._conn() as conn:
        conn.execute("INSERT INTO role_permissions VALUES ('viewer', 'write', NULL)")
        conn.execute("UPDATE cache_version SET version=?", (time.time() + 1,))
        conn.commit()
    assert sec.check_permission("alice", "write")


class MemoryBackend:
    def __init__(self) -> None:
        self.version = 0.0

    def get(self) -> float:
        return self.version

    def set(self, version: float) -> None:
        self.version = version


def test_pluggable_cache_backend(tmp_path, monkeypatch):
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    sec = importlib.reload(security)
    backend = MemoryBackend()
    sec.set_cache_backend(backend)
    sec.define_role("viewer", ["read"])
    sec.assign_role("alice", "viewer")
    assert sec.check_permission("alice", "read")
    with sec._conn() as conn:
        conn.execute(
            "INSERT INTO role_permissions VALUES ('viewer', 'write', NULL)"
        )
        conn.commit()
    backend.set(time.time() + 1)
    assert sec.check_permission("alice", "write")


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, float] = {}

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> bytes | None:
        val = self.store.get(key)
        return None if val is None else str(val).encode()

    def set(self, key: str, value: float) -> None:
        self.store[key] = value


def test_redis_cache_backend(tmp_path, monkeypatch):
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    sec = importlib.reload(security)
    backend = security.RedisCacheBackend(client=FakeRedis())
    sec.set_cache_backend(backend)
    sec.define_role("viewer", ["read"])
    sec.assign_role("alice", "viewer")
    assert sec.check_permission("alice", "read")
    with sec._conn() as conn:
        conn.execute(
            "INSERT INTO role_permissions VALUES ('viewer', 'write', NULL)"
        )
        conn.commit()
    backend.set(time.time() + 1)
    assert sec.check_permission("alice", "write")


class FailingRedis:
    def ping(self) -> bool:  # pragma: no cover - simple stub
        raise RuntimeError("unavailable")


def test_redis_backend_fallback(tmp_path, monkeypatch):
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    sec = importlib.reload(security)
    backend = security.RedisCacheBackend(client=FailingRedis())
    sec.set_cache_backend(backend)
    assert isinstance(sec._cache_backend, security.SQLiteCacheBackend)


def test_cache_backend_health_metric(tmp_path, monkeypatch):
    db = tmp_path / "rbac.db"
    monkeypatch.setenv("FORZIUM_RBAC_DB", str(db))
    mon = importlib.reload(monitoring)
    sec = importlib.reload(security)
    backend = security.RedisCacheBackend(client=FakeRedis())
    sec.set_cache_backend(backend)
    assert mon.get_metric("cache_backend_health") == 1.0
    failing = security.RedisCacheBackend(client=FailingRedis())
    sec.set_cache_backend(failing)
    assert mon.get_metric("cache_backend_health") == 0.0