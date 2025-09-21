"""Minimal middleware implementations for Forzium."""

from __future__ import annotations

import base64
import gzip
import inspect
import hashlib
import hmac
import json
import logging
import math
import mimetypes
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable
from urllib.parse import parse_qs

from infrastructure.monitoring import current_trace_span

from .dependency import Response as FrameworkResponse
from .security import authorize_permissions, decode_jwt, log_event

if TYPE_CHECKING:  # pragma: no cover
    from .dependency import Request
    from .dependency import Response as HTTPResponse
else:  # pragma: no cover - runtime-only import to avoid cycles in typing
    Request = Any
    HTTPResponse = FrameworkResponse


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
    """Configure Cross-Origin Resource Sharing headers."""

    def __init__(
        self,
        allow_origin: str = "*",
        allow_methods: str = "*",
        allow_headers: str = "*",
        allow_credentials: bool = False,
        max_age: int = 600,
    ) -> None:
        self.allow_origin = allow_origin
        self.allow_methods = allow_methods
        self.allow_headers = allow_headers
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        headers.setdefault("access-control-allow-origin", self.allow_origin)
        headers.setdefault("access-control-allow-methods", self.allow_methods)
        headers.setdefault("access-control-allow-headers", self.allow_headers)
        if self.allow_credentials:
            headers.setdefault("access-control-allow-credentials", "true")
        headers.setdefault("access-control-max-age", str(self.max_age))
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set common HTTP security headers."""

    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "x-xss-protection": "1; mode=block",
            "referrer-policy": "same-origin",
        }

    def after_response(
        self, status: int, body: str, headers: dict[str, str]
    ) -> tuple[int, str, dict[str, str]]:
        for key, value in self.headers.items():
            headers.setdefault(key, value)
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
        params = (*params, self.data)
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
        params = (*params, self.data)
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

    def __init__(
        self,
        secret: str,
        scopes: list[str] | None = None,
        permissions: list[str] | None = None,
        permission_mode: str = "all",
    ) -> None:
        super().__init__(secret, require=True)
        self.scopes = scopes or []
        self.permissions = permissions or []
        self.permission_mode = permission_mode

    def before_request(
        self, body: bytes, params: tuple, query: bytes
    ) -> tuple[bytes, tuple, bytes, tuple[int, str, dict[str, str]] | None]:
        params_dict = parse_qs(query.decode()) if query else {}
        token = params_dict.pop("token", [""])[0]
        payload = decode_jwt(token, self.secret) if token else None
        if not isinstance(payload, dict):
            log_event(token or "", "unauthorized")
            return body, params, query, (401, "unauthorized", {})
        scopes = payload.get("scopes", [])
        if any(scope not in scopes for scope in self.scopes):
            log_event(payload.get("user", token or ""), "forbidden")
            return body, params, query, (403, "forbidden", {})
        user = payload.get("user")
        if not authorize_permissions(
            user or "", self.permissions, self.permission_mode
        ):
            log_event(user or "", "forbidden")
            return body, params, query, (403, "forbidden", {})
        log_event(user or "", "authorized")
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


class RequestLoggerMiddleware:
    """ASGI-style middleware emitting structured request logs."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
        *,
        level: int = logging.INFO,
    ) -> None:
        self.logger = logger or logging.getLogger("forzium.request")
        self.level = level

    def _ensure_request_id(self, request: Request) -> str:
        """Return a stable request identifier, generating one if absent."""

        request_id = getattr(request.state, "request_id", None)
        if not request_id:
            request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
            try:
                request.state.request_id = request_id
            except AttributeError:  # pragma: no cover - request has no state namespace
                pass
        return request_id

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], HTTPResponse | Awaitable[HTTPResponse]],
    ) -> HTTPResponse:
        start = time.perf_counter()
        try:
            response = call_next(request)
            if inspect.isawaitable(response):
                response = await response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._log_failure(request, duration_ms, exc)
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        self._log_success(request, response, duration_ms)
        return response

    def _span_fields(self) -> dict[str, str]:
        span = current_trace_span()
        if not span:
            return {}
        try:
            context = span.get_span_context()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - tolerate missing APIs
            return {}
        trace_id = getattr(context, "trace_id", 0)
        span_id = getattr(context, "span_id", 0)
        fields: dict[str, str] = {}
        if trace_id:
            fields["trace_id"] = f"{trace_id:032x}"
        if span_id:
            fields["span_id"] = f"{span_id:016x}"
        return fields

    def _base_payload(self, request: Request, duration_ms: float) -> dict[str, Any]:
        payload = {
            "event": "request",
            "method": getattr(request, "method", "").upper(),
            "path": getattr(request, "url", ""),
            "duration_ms": round(duration_ms, 3),
        }
        payload["request_id"] = self._ensure_request_id(request)
        payload["route"] = getattr(request.state, "route", payload["path"])
        payload["latency_ms"] = payload["duration_ms"]
        payload.update(self._span_fields())
        return payload

    def _log_success(
        self, request: Request, response: HTTPResponse, duration_ms: float
    ) -> None:
        payload = self._base_payload(request, duration_ms)
        payload["status"] = getattr(response, "status_code", 200)
        self.logger.log(
            self.level,
            json.dumps(payload, separators=(",", ":")),
        )

    def _log_failure(
        self, request: Request, duration_ms: float, exc: Exception
    ) -> None:
        payload = self._base_payload(request, duration_ms)
        payload["status"] = 500
        payload["error"] = f"{exc.__class__.__name__}: {exc}"
        self.logger.error(
            json.dumps(payload, separators=(",", ":")),
            exc_info=True,
        )


class RateLimitMiddleware:
    """Enforce configurable request-per-window limits."""

    def __init__(
        self,
        limit: int,
        window: float = 1.0,
        *,
        per_client: bool = True,
        include_path: bool = False,
        identifier: Callable[[Request], str] | None = None,
        timer: Callable[[], float] | None = None,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window <= 0:
            raise ValueError("window must be positive")
        self.limit = limit
        self.window = window
        self.per_client = per_client
        self.include_path = include_path
        self._identifier = identifier
        self._timer = timer or time.monotonic
        self._history: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _client_identifier(self, request: Request) -> str:
        if self._identifier is not None:
            return self._identifier(request)
        headers = getattr(request, "headers", {}) or {}
        for header in (
            "x-forwarded-for",
            "x-real-ip",
            "cf-connecting-ip",
            "client-ip",
            "remote-addr",
        ):
            raw = headers.get(header)
            if raw:
                return str(raw).split(",")[0].strip()
        return "global"

    def _key_for(self, request: Request) -> str:
        base = "global"
        if self.per_client:
            base = self._client_identifier(request)
        if not self.include_path:
            return base
        url = str(getattr(request, "url", "/"))
        path = url.split("?", 1)[0]
        return f"{base}:{path}" if self.per_client else path

    def _acquire(
        self, request: Request
    ) -> tuple[bool, float, int, float]:
        key = self._key_for(request)
        now = self._timer()
        with self._lock:
            bucket = self._history[key]
            cutoff = now - self.window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = (bucket[0] + self.window) - now
                reset = max(0.0, retry_after)
                return False, max(0.0, retry_after), 0, reset
            bucket.append(now)
            remaining = max(0, self.limit - len(bucket))
            reset = (bucket[0] + self.window) - now if bucket else self.window
            return True, 0.0, remaining, max(0.0, reset)

    def _attach_headers(self, response: HTTPResponse, remaining: int, reset: float) -> None:
        headers = getattr(response, "headers", None)
        if headers is None:
            return
        headers["x-ratelimit-limit"] = str(self.limit)
        headers["x-ratelimit-remaining"] = str(max(0, remaining))
        headers["x-ratelimit-reset"] = str(max(0, math.ceil(reset)))

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], HTTPResponse | Awaitable[HTTPResponse]],
    ) -> HTTPResponse:
        allowed, retry_after, remaining, reset = self._acquire(request)
        if not allowed:
            retry_after_seconds = max(0.0, retry_after)
            retry_after_header = str(max(0, math.ceil(retry_after_seconds)))
            headers = {
                "retry-after": retry_after_header,
                "x-ratelimit-limit": str(self.limit),
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": str(max(0, math.ceil(reset))),
            }
            payload = json.dumps({"detail": "Too Many Requests"})
            return FrameworkResponse(
                payload,
                status_code=429,
                headers=headers,
                media_type="application/json",
            )
        response = call_next(request)
        if inspect.isawaitable(response):
            response = await response
        self._attach_headers(response, remaining, reset)
        return response


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
        content = file_path.read_bytes()
        media_type = mimetypes.guess_type(str(file_path))[0] or "text/plain"
        headers = {
            "content-type": media_type,
            "content-length": str(len(content)),
        }
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
    "RequestLoggerMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "StaticFilesMiddleware",
]