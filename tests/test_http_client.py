"""Minimal HTTP client using the standard library."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode


@dataclass
class Response:
    """HTTP response container."""

    status_code: int
    text: str
    headers: dict[str, str]
    content: bytes

    def json(self) -> object:
        """Return the response body parsed as JSON."""
        return json.loads(self.text)


def _normalize_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """Return a case-insensitive mapping as lower-case keys."""

    if headers is None:
        return {}
    return {k.lower(): v.strip() for k, v in headers.items()}


def _apply_query(url: str, params: Mapping[str, object] | None) -> str:
    """Return *url* with encoded *params* appended."""

    if not params:
        return url
    encoded = urlencode(params)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{encoded}"


def get(
    url: str,
    *,
    params: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Send an HTTP GET request."""

    request = urllib.request.Request(
        _apply_query(url, params),
        headers=dict(headers or {}),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request) as resp:
            raw = resp.read()
            try:
                text = raw.decode()
            except UnicodeDecodeError:
                text = raw.decode("latin1")
            return Response(
                resp.getcode(),
                text,
                _normalize_headers(resp.headers),
                raw,
            )
    except HTTPError as exc:
        raw = exc.read()
        try:
            text = raw.decode()
        except UnicodeDecodeError:
            text = raw.decode("latin1")
        return Response(
            exc.code,
            text,
            _normalize_headers(exc.headers),
            raw,
        )


def post(
    url: str,
    payload: Mapping[str, object],
    *,
    params: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Send an HTTP POST request with a JSON payload."""

    data = json.dumps(payload).encode()
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        _apply_query(url, params),
        data=data,
        method="POST",
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            try:
                text = raw.decode()
            except UnicodeDecodeError:
                text = raw.decode("latin1")
            return Response(
                resp.getcode(),
                text,
                _normalize_headers(resp.headers),
                raw,
            )
    except HTTPError as exc:
        raw = exc.read()
        try:
            text = raw.decode()
        except UnicodeDecodeError:
            text = raw.decode("latin1")
        return Response(
            exc.code,
            text,
            _normalize_headers(exc.headers),
            raw,
        )
