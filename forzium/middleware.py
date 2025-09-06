"""Minimal middleware implementations for Forzium."""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs

from .security import decode_jwt


class BaseHTTPMiddleware:
    """Process request and response phases."""

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        """Hook executed before the endpoint."""
        return body, params, query, None

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        """Hook executed after the endpoint."""
        return status, body, headers


class CORSMiddleware(BaseHTTPMiddleware):
    """Add a permissive CORS header."""

    def __init__(self, allow_origin: str = "*") -> None:
        self.allow_origin = allow_origin

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        headers.setdefault("access-control-allow-origin", self.allow_origin)
        return status, body, headers


class GZipMiddleware(BaseHTTPMiddleware):
    """Compress the response body using gzip."""

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        data = body.encode()
        body = gzip.compress(data).decode("latin1")
        headers["content-encoding"] = "gzip"
        return status, body, headers


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect plain HTTP requests to HTTPS."""

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        params_dict = parse_qs(query.decode()) if query else {}
        url = params_dict.get("url", [""])[0]
        if url.startswith("http://"):
            target = "https://" + url[7:]
            return body, params, query, (307, "", {"location": target})
        return body, params, query, None


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """Permit only configured host names."""

    def __init__(self, allowed_hosts: Iterable[str]) -> None:
        self.allowed = set(allowed_hosts)

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        params_dict = parse_qs(query.decode()) if query else {}
        host = params_dict.get("host", [""])[0]
        if host and host not in self.allowed:
            return body, params, query, (400, "host not allowed", {})
        return body, params, query, None


class SessionMiddleware(BaseHTTPMiddleware):
    """Persist session data in a signed cookie."""

    def __init__(self, secret: str, cookie_name: str = "session") -> None:
        self.secret = secret.encode()
        self.cookie_name = cookie_name
        self.data: dict[str, Any] = {}

    def _decode(self, value: str) -> None:
        try:
            raw, sig = value.split(".")
            expected = hmac.new(
                self.secret,
                raw.encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(sig, expected):
                return
            decoded = base64.urlsafe_b64decode(raw.encode()).decode()
            self.data = json.loads(decoded)
        except Exception:  # pragma: no cover - invalid cookie
            self.data = {}

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        params_dict = parse_qs(query.decode()) if query else {}
        cookie = params_dict.pop(self.cookie_name, [""])[0]
        if cookie:
            self._decode(cookie)
        params = (self.data, *params)
        query = (
            "&".join(f"{k}={v[0]}" for k, v in params_dict.items()).encode()
            if params_dict
            else b""
        )
        return body, params, query, None

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        raw = base64.urlsafe_b64encode(
            json.dumps(self.data).encode(),
        ).decode()
        sig = hmac.new(
            self.secret,
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()
        headers["set-cookie"] = f"{self.cookie_name}={raw}.{sig}"
        return status, body, headers


class FileSessionMiddleware(BaseHTTPMiddleware):
    """Persist session data in a JSON file keyed by session id."""

    def __init__(self, path: str, cookie_name: str = "session_id") -> None:
        self.path = Path(path)
        self.cookie_name = cookie_name
        if not self.path.exists():
            self.path.write_text("{}")
        self.sid: str | None = None
        self.data: dict[str, Any] = {}

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        params_dict = parse_qs(query.decode()) if query else {}
        sid = params_dict.pop(self.cookie_name, [""])[0]
        sessions = json.loads(self.path.read_text())
        self.sid = sid or uuid.uuid4().hex
        self.data = sessions.get(self.sid, {})
        params = (self.data, *params)
        query = (
            "&".join(f"{k}={v[0]}" for k, v in params_dict.items()).encode()
            if params_dict
            else b""
        )
        return body, params, query, None

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        sessions = json.loads(self.path.read_text())
        sessions[self.sid or ""] = self.data
        self.path.write_text(json.dumps(sessions))
        headers["set-cookie"] = f"{self.cookie_name}={self.sid}"
        return status, body, headers


class JWTMiddleware(BaseHTTPMiddleware):
    """Decode a JWT from query parameters and inject the payload."""

    def __init__(self, secret: str, require: bool = False) -> None:
        self.secret = secret
        self.require = require

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        params_dict = parse_qs(query.decode()) if query else {}
        token = params_dict.pop("token", [""])[0]
        payload = decode_jwt(token, self.secret) if token else None
        if self.require and not isinstance(payload, dict):
            return body, params, query, (401, "unauthorized", {})
        user = payload.get("user") if isinstance(payload, dict) else None
        params = (user, *params)
        query = (
            "&".join(f"{k}={v[0]}" for k, v in params_dict.items()).encode()
            if params_dict
            else b""
        )
        return body, params, query, None


class JWTAuthMiddleware(JWTMiddleware):
    """Require a JWT and optionally enforce authorization scopes."""

    def __init__(self, secret: str, scopes: list[str] | None = None) -> None:
        super().__init__(secret, require=True)
        self.scopes = scopes or []

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        params_dict = parse_qs(query.decode()) if query else {}
        token = params_dict.pop("token", [""])[0]
        payload = decode_jwt(token, self.secret) if token else None
        if not isinstance(payload, dict):
            return body, params, query, (401, "unauthorized", {})
        scopes = payload.get("scopes", [])
        if any(scope not in scopes for scope in self.scopes):
            return body, params, query, (403, "forbidden", {})
        user = payload.get("user")
        params = (user, *params)
        query = (
            "&".join(f"{k}={v[0]}" for k, v in params_dict.items()).encode()
            if params_dict
            else b""
        )
        return body, params, query, None


class LoggingMiddleware(BaseHTTPMiddleware):
    """Invoke *logger* around request processing."""

    def __init__(self, logger: Callable[[str], None]) -> None:
        self.logger = logger

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        self.logger("request")
        return body, params, query, None

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        self.logger(f"response {status}")
        return status, body, headers


class StaticFilesMiddleware(BaseHTTPMiddleware):
    """Serve files under *prefix* from *directory*."""

    def __init__(self, directory: str, prefix: str = "/static") -> None:
        self.directory = Path(directory)
        self.prefix = prefix.strip("/")

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        if not params:
            return body, params, query, None
        path = str(params[0])
        if not path.startswith(self.prefix + "/"):
            return body, params, query, None
        rel_path = path[len(self.prefix) + 1 :]
        file_path = self.directory / rel_path
        if file_path.is_dir():
            file_path = file_path / "index.html"
        if not file_path.exists():
            return body, params, query, (404, "not found", {})
        content = file_path.read_text()
        media_type = mimetypes.guess_type(str(file_path))[0] or "text/plain"
        headers = {"content-type": media_type}
        return body, params, query, (200, content, headers)


__all__ = [
    "BaseHTTPMiddleware",
    "CORSMiddleware",
    "GZipMiddleware",
    "HTTPSRedirectMiddleware",
    "TrustedHostMiddleware",
    "SessionMiddleware",
    "FileSessionMiddleware",
    "JWTMiddleware",
    "JWTAuthMiddleware",
    "LoggingMiddleware",
    "StaticFilesMiddleware",
]
