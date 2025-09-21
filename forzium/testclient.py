"""Simple in-memory HTTP client for ForziumApp."""

from __future__ import annotations

import json
import re
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
    content: bytes
    chunks: list[str] | None = None

    def json(self) -> Any:
        """Return the body parsed as JSON."""
        return json.loads(self.text)


class TestClient:
    """Execute requests against a ``ForziumApp`` without a server."""

    __test__ = False  # prevent Pytest from treating this as a test case
    
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
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        """Send an HTTP request and return the response."""
        def match_path(
            template: str, concrete: str
        ) -> tuple[bool, tuple[str, ...]]:
            if "{" not in template:
                return template == concrete, ()
            pattern_parts: list[str] = []
            idx = 0
            length = len(template)
            while idx < length:
                if template[idx] == "{":
                    end = template.find("}", idx)
                    if end == -1:
                        pattern_parts.append(re.escape(template[idx:]))
                        idx = length
                        break
                    pattern_parts.append(r"([^/]+)")
                    idx = end + 1
                    continue
                next_brace = template.find("{", idx)
                if next_brace == -1:
                    next_brace = length
                pattern_parts.append(re.escape(template[idx:next_brace]))
                idx = next_brace
            pattern = "^" + "".join(pattern_parts) + "$"
            match = re.match(pattern, concrete)
            if match is None:
                return False, ()
            return True, match.groups()

        route = None
        path_params: tuple[str, ...] = ()
        for r in self.app.routes:
            if r["method"] != method:
                continue
            matched, values = match_path(r["path"], path)
            if matched:
                route = r
                path_params = values
                break
        if route is None:
            raise ValueError(f"no route for {method} {path}")
        route_app = route.get("app", self.app)
        overrides = [route.get("dependency_overrides", {})]
        if route.get("use_parent_overrides", True):
            overrides.append(self.app.dependency_overrides)
        handler = route_app._make_handler(  # pylint: disable=protected-access
            route["func"],
            route["param_names"],
            route["param_converters"],
            route["query_params"],
            route.get("body_param"),
            route["dependencies"],
            route.get("expects_request", False),
            route["method"],
            route["path"],
            route.get("background_param"),
            overrides,
        )
        if body is not None and json_body is not None:
            raise ValueError("provide either json_body or body")
        body_bytes = (
            body
            if body is not None
            else json.dumps(json_body).encode()
            if json_body
            else b""
        )
        query = urlencode(params or {}).encode()
        status, body_obj, resp_headers = handler(
            body_bytes, path_params, query, dict(headers or {})
        )
        if isinstance(body_obj, list):
            text = "".join(body_obj)
            content = text.encode("latin1")
            chunks = body_obj
        elif isinstance(body_obj, bytes):
            content = body_obj
            try:
                text = content.decode()
            except UnicodeDecodeError:
                text = content.decode("latin1")
            chunks = None
        else:
            text = body_obj
            content = text.encode()
            chunks = None
        return Response(status, text, resp_headers, content, chunks)

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        """Send a GET request."""
        return self.request("GET", path, params=params, headers=headers)

    def post(
        self,
        path: str,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        """Send a POST request."""
        return self.request(
            "POST", path, json_body=json_body, params=params, headers=headers
        )

    def head(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        """Send a HEAD request."""
        return self.request("HEAD", path, params=params, headers=headers)


__all__ = ["Response", "TestClient"]