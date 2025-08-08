"""Simple in-memory HTTP client for ForziumApp."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode

from .app import ForziumApp


@dataclass
class Response:
    """Container for HTTP response data."""

    status_code: int
    text: str
    headers: Mapping[str, str]

    def json(self) -> Any:
        """Return the body parsed as JSON."""
        return json.loads(self.text)


class TestClient:
    """Execute requests against a ``ForziumApp`` without a server."""

    def __init__(self, app: ForziumApp) -> None:
        self.app = app

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        body: bytes | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Response:
        """Send an HTTP request and return the response."""
        route = next(
            (r for r in self.app.routes if r["method"] == method and r["path"] == path),
            None,
        )
        if route is None:
            raise ValueError(f"no route for {method} {path}")
        handler = self.app._make_handler(  # pylint: disable=protected-access
            route["func"],
            route["param_names"],
            route["param_converters"],
            route["query_params"],
            route["expects_body"],
            route["dependencies"],
            route.get("expects_request", False),
            route["method"],
            route["path"],
            route.get("background_param"),
            [route.get("dependency_overrides", {}), self.app.dependency_overrides],
        )
        if body is not None and json_body is not None:
            raise ValueError("provide either json_body or body")
        body_bytes = (
            body
            if body is not None
            else json.dumps(json_body).encode() if json_body else b""
        )
        query = urlencode(params or {}).encode()
        status, body_str, headers = handler(body_bytes, (), query)
        return Response(status, body_str, headers)

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Response:
        """Send a GET request."""
        return self.request("GET", path, params=params)

    def post(
        self,
        path: str,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Response:
        """Send a POST request."""
        return self.request("POST", path, json_body=json_body, params=params)


__all__ = ["Response", "TestClient"]
