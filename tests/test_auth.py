"""Tests for JWT middleware and password utilities."""

import base64

from forzium.middleware import JWTAuthMiddleware, JWTMiddleware
from forzium.security import (
    authorize_scopes,
    create_jwt,
    decode_jwt,
    is_token_revoked,
    hash_password,
    refresh_jwt,
    revoke_token,
    rotate_jwt,
    verify_password,
)
from forzium.auth import (
    get_api_key,
    get_bearer_token,
    oauth2_authorization_code_flow,
    oauth2_client_credentials_flow,
    oauth2_implicit_flow,
    oauth2_password_flow,
    parse_basic_auth,
)


def test_jwt_auth_middleware() -> None:
    token = create_jwt({"user": "alice"}, "s")
    mw = JWTAuthMiddleware(secret="s")
    _, params, _, resp = mw.before_request(b"", (), f"token={token}".encode())
    assert resp is None and params[0] == "alice"
    _, _, _, resp = mw.before_request(b"", (), b"")
    assert resp == (401, "unauthorized", {})


def test_jwt_scopes_and_refresh() -> None:
    payload = {"user": "bob", "scopes": ["read"]}
    access = create_jwt(payload, "a")
    refresh = create_jwt(payload, "r")
    assert authorize_scopes(access, "a", ["read"])
    assert not authorize_scopes(access, "a", ["write"])
    new_access = refresh_jwt(refresh, "a", "r")
    assert decode_jwt(new_access or "", "a") == payload


def test_password_hashing() -> None:
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("bad", hashed)


def test_revocation_and_rotation() -> None:
    payload = {"user": "carol"}
    token = create_jwt(payload, "s1")
    assert decode_jwt(token, "s1") == payload
    revoke_token(token)
    assert is_token_revoked(token)
    assert decode_jwt(token, "s1") is None
    payload2 = {"user": "carol", "v": 1}
    token2 = create_jwt(payload2, "s1")
    new_token = rotate_jwt(token2, "s1", "s2")
    assert new_token is not None
    assert decode_jwt(token2, "s1") is None
    assert decode_jwt(new_token or "", "s2") == payload2


def test_basic_and_bearer_parsing() -> None:
    creds = base64.b64encode(b"alice:secret").decode()
    assert parse_basic_auth(f"Basic {creds}") == ("alice", "secret")
    assert parse_basic_auth("Bearer x") is None
    assert get_bearer_token("Bearer t1") == "t1"
    assert get_bearer_token("Basic y") is None


def test_api_key_sources() -> None:
    headers = {"X-API-Key": "h"}
    assert get_api_key(headers, {}, {}) == "h"
    assert get_api_key({}, {"api_key": "q"}, {}) == "q"
    assert get_api_key({}, {}, {"api_key": "c"}) == "c"
    assert get_api_key({}, {}, {}) is None


def test_oauth2_flows() -> None:
    def verify_user(u: str, p: str) -> bool:
        return u == "u" and p == "p"

    def verify_client(cid: str, cs: str) -> bool:
        return cid == "id" and cs == "sec"

    def resolve(code: str) -> str | None:
        return "bob" if code == "ok" else None

    secret = "s"
    t1 = oauth2_password_flow("u", "p", verify_user, secret)
    assert decode_jwt(t1 or "", secret)["sub"] == "u"
    t2 = oauth2_client_credentials_flow("id", "sec", verify_client, secret)
    assert decode_jwt(t2 or "", secret)["client_id"] == "id"
    t3 = oauth2_authorization_code_flow("ok", resolve, secret)
    assert decode_jwt(t3 or "", secret)["sub"] == "bob"
    t4 = oauth2_implicit_flow("alice", secret)
    assert decode_jwt(t4, secret)["sub"] == "alice"
