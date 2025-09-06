"""Security helpers including JWT, RBAC, and audit logging."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from typing import Any, Dict, Iterable, List

_revoked_tokens: set[str] = set()

DB_PATH = os.getenv("FORZIUM_RBAC_DB", "rbac.db")


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS roles (name TEXT)")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS role_permissions (role TEXT, perm TEXT)"
        )
        cur.execute("CREATE TABLE IF NOT EXISTS user_roles (user TEXT, role TEXT)")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS audit_log (token TEXT, action TEXT, ts REAL)"
        )
        conn.commit()


init_db()


def log_token_event(token: str, action: str) -> None:
    """Record *action* performed on *token* with timestamp."""

    with _conn() as conn:
        conn.execute(
            "INSERT INTO audit_log VALUES (?, ?, ?)",
            (token, action, time.time()),
        )
        conn.commit()


def get_audit_log(token: str | None = None) -> List[Dict[str, Any]]:
    """Return audit log entries filtered by *token* if provided."""

    with _conn() as conn:
        cur = conn.cursor()
        if token:
            cur.execute(
                "SELECT token, action, ts FROM audit_log WHERE token=? ORDER BY ts",
                (token,),
            )
        else:
            cur.execute("SELECT token, action, ts FROM audit_log ORDER BY ts")
        rows = cur.fetchall()
    return [{"token": t, "action": a, "ts": ts} for t, a, ts in rows]


def define_role(name: str, permissions: Iterable[str]) -> None:
    """Register role *name* with iterable *permissions*."""

    with _conn() as conn:
        conn.execute("INSERT INTO roles VALUES (?)", (name,))
        conn.executemany(
            "INSERT INTO role_permissions VALUES (?, ?)",
            [(name, p) for p in permissions],
        )
        conn.commit()


def assign_role(user: str, role: str) -> None:
    """Assign existing *role* to *user*."""

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM roles WHERE name=?", (role,))
        if not cur.fetchone():
            raise KeyError(role)
        cur.execute("INSERT OR IGNORE INTO user_roles VALUES (?, ?)", (user, role))
        conn.commit()


def check_permission(user: str, permission: str) -> bool:
    """Return True if *user* possesses *permission*."""

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM user_roles ur
            JOIN role_permissions rp ON ur.role = rp.role
            WHERE ur.user=? AND rp.perm=? LIMIT 1
            """,
            (user, permission),
        )
        return cur.fetchone() is not None


def list_roles() -> List[str]:
    """Return all defined role names."""

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM roles")
        return [r[0] for r in cur.fetchall()]


def list_user_roles(user: str) -> List[str]:
    """Return roles assigned to *user*."""

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT role FROM user_roles WHERE user=?", (user,))
        return [r[0] for r in cur.fetchall()]


def remove_role(user: str, role: str) -> None:
    """Remove *role* assignment from *user*."""

    with _conn() as conn:
        conn.execute(
            "DELETE FROM user_roles WHERE user=? AND role=?",
            (user, role),
        )
        conn.commit()


def delete_role(name: str) -> None:
    """Delete role *name* and its assignments."""

    with _conn() as conn:
        conn.execute("DELETE FROM roles WHERE name=?", (name,))
        conn.execute("DELETE FROM role_permissions WHERE role=?", (name,))
        conn.execute("DELETE FROM user_roles WHERE role=?", (name,))
        conn.commit()


def create_jwt(payload: Dict[str, Any], secret: str) -> str:
    """Encode *payload* as a JWT using HS256."""

    header = {"alg": "HS256", "typ": "JWT"}

    def b64(obj: Dict[str, Any]) -> str:
        data = json.dumps(obj, separators=(",", ":"))
        return base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")

    signing_input = f"{b64(header)}.{b64(payload)}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    token = f"{signing_input.decode()}.{sig_b64}"
    log_token_event(token, "created")
    return token


def decode_jwt(token: str, secret: str) -> Dict[str, Any] | None:
    """Decode *token* and return payload if valid and not revoked."""

    if token in _revoked_tokens:
        return None
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(sig_b64 + "==")
        if not hmac.compare_digest(expected, signature):
            return None
        payload_json = base64.urlsafe_b64decode(payload_b64 + "==")
        return json.loads(payload_json)
    except Exception:
        return None


def authorize_scopes(token: str, secret: str, required: Iterable[str]) -> bool:
    """Return True if *token* carries all *required* scopes."""

    payload = decode_jwt(token, secret)
    if not isinstance(payload, dict):
        return False
    token_scopes = payload.get("scopes", [])
    return all(scope in token_scopes for scope in required)


def refresh_jwt(
    refresh_token: str, access_secret: str, refresh_secret: str
) -> str | None:
    """Generate a new access token using *refresh_token*."""

    payload = decode_jwt(refresh_token, refresh_secret)
    if not isinstance(payload, dict):
        return None
    new_token = create_jwt(payload, access_secret)
    log_token_event(new_token, "refreshed")
    return new_token


def revoke_token(token: str) -> None:
    """Add *token* to the revocation set."""

    _revoked_tokens.add(token)
    log_token_event(token, "revoked")


def is_token_revoked(token: str) -> bool:
    """Return True if *token* has been revoked."""

    return token in _revoked_tokens


def rotate_jwt(token: str, old_secret: str, new_secret: str) -> str | None:
    """Re-sign *token* with *new_secret* and revoke the old one."""

    payload = decode_jwt(token, old_secret)
    if not isinstance(payload, dict):
        return None
    revoke_token(token)
    new_token = create_jwt(payload, new_secret)
    log_token_event(new_token, "rotated")
    return new_token


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash *password* using PBKDF2-HMAC-SHA256."""

    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return base64.urlsafe_b64encode(salt + digest).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches *hashed*."""

    try:
        data = base64.urlsafe_b64decode(hashed.encode())
        salt, digest = data[:16], data[16:]
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(digest, check)
    except Exception:
        return False


__all__ = [
    "assign_role",
    "authorize_scopes",
    "check_permission",
    "create_jwt",
    "decode_jwt",
    "define_role",
    "delete_role",
    "get_audit_log",
    "hash_password",
    "log_token_event",
    "list_roles",
    "list_user_roles",
    "refresh_jwt",
    "revoke_token",
    "is_token_revoked",
    "remove_role",
    "rotate_jwt",
    "verify_password",
]
