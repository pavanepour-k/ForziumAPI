"""Authentication scheme helpers for OAuth2 and HTTP auth."""

from __future__ import annotations

import base64
from typing import Callable, Dict, Iterable, Tuple

from .security import create_jwt


def parse_basic_auth(header: str | None) -> Tuple[str, str] | None:
    """Decode HTTP Basic *header* into ``(user, password)``."""

    if not header:
        return None
    scheme, _, data = header.partition(" ")
    if scheme.lower() != "basic" or not data:
        return None
    try:
        decoded = base64.b64decode(data.encode()).decode()
        user, _, pw = decoded.partition(":")
        if not _:
            return None
        return user, pw
    except Exception:
        return None


def get_bearer_token(header: str | None) -> str | None:
    """Return Bearer token from Authorization *header* if present."""

    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_api_key(
    headers: Dict[str, str],
    query: Dict[str, str],
    cookies: Dict[str, str],
    name: str = "api_key",
) -> str | None:
    """Fetch API key named *name* from headers, query, or cookies."""

    key = headers.get("X-API-Key")
    if not key:
        auth = headers.get("Authorization", "")
        if auth.startswith("Key "):
            key = auth[4:]
    if not key:
        key = query.get(name)
    if not key:
        key = cookies.get(name)
    return key


def oauth2_password_flow(
    username: str,
    password: str,
    verify: Callable[[str, str], bool],
    secret: str,
    scopes: Iterable[str] | None = None,
) -> str | None:
    """Issue token if ``verify`` accepts *username* and *password*."""

    if not verify(username, password):
        return None
    payload = {"sub": username}
    if scopes:
        payload["scopes"] = list(scopes)
    return create_jwt(payload, secret)


def oauth2_client_credentials_flow(
    client_id: str,
    client_secret: str,
    verify: Callable[[str, str], bool],
    secret: str,
    scopes: Iterable[str] | None = None,
) -> str | None:
    """Issue token if ``verify`` accepts *client_id* and *client_secret*."""

    if not verify(client_id, client_secret):
        return None
    payload = {"client_id": client_id}
    if scopes:
        payload["scopes"] = list(scopes)
    return create_jwt(payload, secret)


def oauth2_authorization_code_flow(
    code: str,
    resolve_user: Callable[[str], str | None],
    secret: str,
    scopes: Iterable[str] | None = None,
) -> str | None:
    """Exchange *code* for token using *resolve_user* callback."""

    user = resolve_user(code)
    if not user:
        return None
    payload = {"sub": user}
    if scopes:
        payload["scopes"] = list(scopes)
    return create_jwt(payload, secret)


def oauth2_implicit_flow(
    user: str,
    secret: str,
    scopes: Iterable[str] | None = None,
) -> str:
    """Directly issue token for *user* in implicit flow."""

    payload = {"sub": user}
    if scopes:
        payload["scopes"] = list(scopes)
    return create_jwt(payload, secret)


__all__ = [
    "parse_basic_auth",
    "get_bearer_token",
    "get_api_key",
    "oauth2_password_flow",
    "oauth2_client_credentials_flow",
    "oauth2_authorization_code_flow",
    "oauth2_implicit_flow",
]
