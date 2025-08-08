"""Specialized HTTP responses and status utilities."""

from __future__ import annotations

import json
import mimetypes
import os
from typing import Any, Iterable, Mapping

from .dependency import BackgroundTask, BackgroundTasks, Response


class JSONResponse(Response):
    """Serialize content to JSON."""

    def __init__(
        self,
        content: Any,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
    ) -> None:
        body = json.dumps(content).encode()
        super().__init__(
            body,
            status_code=status_code,
            headers=headers,
            media_type="application/json",
            background=background,
        )


class PlainTextResponse(Response):
    """Return plain text content."""

    def __init__(
        self,
        content: str,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
    ) -> None:
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type="text/plain; charset=utf-8",
            background=background,
        )


class HTMLResponse(Response):
    """Return HTML content."""

    def __init__(
        self,
        content: str,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
    ) -> None:
        super().__init__(
            content,
            status_code=status_code,
            headers=headers,
            media_type="text/html; charset=utf-8",
            background=background,
        )


class RedirectResponse(Response):
    """Redirect to a different URL."""

    def __init__(
        self,
        url: str,
        *,
        status_code: int = 307,
        headers: Mapping[str, str] | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
    ) -> None:
        hdrs = {"location": url, **(headers or {})}
        super().__init__(
            b"",
            status_code=status_code,
            headers=hdrs,
            background=background,
        )


class FileResponse(Response):
    """Send a file as the response body."""

    def __init__(
        self,
        path: str,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
    ) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, "rb") as f:
            data = f.read()
        mt = media_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        hdrs = {"content-length": str(len(data)), **(headers or {})}
        super().__init__(
            data,
            status_code=status_code,
            headers=hdrs,
            media_type=mt,
            background=background,
        )


class StreamingResponse(Response):
    """Return streaming content from an iterator."""

    def __init__(
        self,
        content: Iterable[bytes],
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
    ) -> None:
        super().__init__(
            b"",
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )
        self._content = content

    def body_iter(self) -> Iterable[bytes]:
        """Yield response body chunks."""

        for chunk in self._content:
            yield chunk

    def serialize(self) -> tuple[int, bytes, dict[str, str]]:
        body = b"".join(self.body_iter())
        return self.status_code, body, self.headers


HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_204_NO_CONTENT = 204
HTTP_400_BAD_REQUEST = 400
HTTP_404_NOT_FOUND = 404
HTTP_500_INTERNAL_SERVER_ERROR = 500


class HTTPException(Exception):
    """Error carrying an HTTP status code and optional headers."""

    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = dict(headers or {})


__all__ = [
    "FileResponse",
    "HTTPException",
    "HTMLResponse",
    "JSONResponse",
    "PlainTextResponse",
    "RedirectResponse",
    "StreamingResponse",
    "HTTP_200_OK",
    "HTTP_201_CREATED",
    "HTTP_204_NO_CONTENT",
    "HTTP_400_BAD_REQUEST",
    "HTTP_404_NOT_FOUND",
    "HTTP_500_INTERNAL_SERVER_ERROR",
]
