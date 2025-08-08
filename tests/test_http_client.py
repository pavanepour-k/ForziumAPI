"""Minimal HTTP client using the standard library."""

from __future__ import annotations

import json
from dataclasses import dataclass
import urllib.request
from urllib.error import HTTPError


@dataclass
class Response:
    """HTTP response container."""

    status_code: int
    text: str

    def json(self) -> object:
        """Return the response body parsed as JSON."""
        return json.loads(self.text)


def get(url: str) -> Response:
    """Send an HTTP GET request."""
    try:
        with urllib.request.urlopen(url) as resp:
            text = resp.read().decode()
            return Response(resp.getcode(), text)
    except HTTPError as exc:
        return Response(exc.code, exc.read().decode())


def post(url: str, payload: dict) -> Response:
    """Send an HTTP POST request with a JSON payload."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode()
            return Response(resp.getcode(), text)
    except HTTPError as exc:
        return Response(exc.code, exc.read().decode())
