# flake8: noqa
"""Minimal HTTP primitives with header and cookie support."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from http.cookies import SimpleCookie
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Tuple,
    cast,
)
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit


def _parse_header(line: str) -> tuple[str, Dict[str, str]]:
    """Parse a Content-Disposition header.

    This replaces :func:`cgi.parse_header` removed from the standard library.
    Only the subset required for multipart form parsing is implemented.
    """
    parts = [p.strip() for p in line.split(";") if p]
    value = parts[0] if parts else ""
    params: Dict[str, str] = {}
    for item in parts[1:]:
        if "=" in item:
            k, v = item.split("=", 1)
            params[k.strip()] = v.strip().strip('"')
    return value, params


class Request:
    """Represent an incoming HTTP request."""

    def __init__(
        self,
        method: str = "GET",
        url: str = "/",
        body: bytes = b"",
        headers: Mapping[str, str] | None = None,
        path_params: Mapping[str, str] | None = None,
        max_upload_size: int | None = None,
        allowed_mime_types: set[str] | None = None,
    ) -> None:
        self.method = method.upper()
        self.url = url
        self._body = body
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.path_params = dict(path_params or {})
        parts = urlsplit(url)
        parsed_items = parse_qs(parts.query).items()
        self.query_params = {
            k: (v[0] if len(v) == 1 else v) for k, v in parsed_items  # noqa: E501
        }
        self._cookies: dict[str, str] | None = None
        self._form_data: dict[str, Any] | None = None
        self._files: dict[str, dict[str, Any]] | None = None
        self._stream_consumed = False
        self.max_upload_size = max_upload_size
        self.allowed_mime_types = allowed_mime_types
        self.state: SimpleNamespace = SimpleNamespace()

    async def body(self) -> bytes:
        """Return the request body."""
        return self._body

    async def json(self) -> Any:
        """Return the JSON-decoded body if present."""
        data = await self.body()
        if not data:
            return None
        return json.loads(data.decode())

    async def form(self) -> dict[str, Any]:
        """Return form data parsed from the body."""

        if self._form_data is not None:
            return self._form_data

        data = await self.body()
        ctype = self.headers.get("content-type", "")
        if ctype.startswith("multipart/form-data") or data.startswith(b"--"):
            boundary = (
                ctype.split("boundary=")[-1] if "boundary=" in ctype else ""
            )  # noqa: E501
            if not boundary:
                line = data.split(b"\r\n", 1)[0]
                if line.startswith(b"--"):
                    boundary = line[2:].decode()
            form: dict[str, Any] = {}
            files: dict[str, dict[str, Any]] = {}
            if boundary:
                delim = ("--" + boundary).encode()
                parts = data.split(delim)[1:-1]
                for part in parts:
                    header_block, content = part.split(b"\r\n\r\n", 1)
                    headers = header_block.decode().split("\r\n")
                    disp = next(
                        (
                            h
                            for h in headers
                            if h.lower().startswith("content-disposition")
                        ),
                        "",
                    )
                    ctype_header = next(
                        (
                            h
                            for h in headers
                            if h.lower().startswith("content-type")
                        ),
                        "",
                    )
                    mime = ctype_header.split(":", 1)[1].strip().lower() if ctype_header else ""
                    _, params = _parse_header(disp)
                    name = params.get("name", "")
                    filename = params.get("filename")
                    content = content.rstrip(b"\r\n")
                    if filename:
                        if (
                            self.allowed_mime_types is not None
                            and mime not in self.allowed_mime_types
                        ):
                            raise ValueError("unsupported media type")
                        if (
                            self.max_upload_size is not None
                            and len(content) > self.max_upload_size
                        ):
                            raise ValueError("file too large")
                        files[name] = {
                            "filename": filename,
                            "content": content,
                            "content_type": mime,
                        }
                    else:
                        form[name] = content.decode()
            self._form_data = form
            self._files = files
        else:
            self._form_data = {
                k: v[0] if len(v) == 1 else v
                for k, v in parse_qs(data.decode()).items()
            }
            self._files = {}
        return self._form_data

    async def stream(self) -> AsyncIterator[bytes]:
        """Yield the body content as a byte stream."""
        if not self._stream_consumed:
            self._stream_consumed = True
            yield self._body

    @property
    def cookies(self) -> dict[str, str]:
        """Lazily parse cookies from the request headers."""
        if self._cookies is None:
            raw = self.headers.get("cookie", "")
            jar: SimpleCookie = SimpleCookie()
            jar.load(raw)
            self._cookies = {k: morsel.value for k, morsel in jar.items()}
        return self._cookies

    @property
    def files(self) -> dict[str, dict[str, Any]]:
        """Return uploaded files parsed from the body."""

        return self._files or {}


class Depends:
    """Wrapper marking a callable as a dependency."""

    def __init__(self, dependency: Callable[..., Any] | None = None) -> None:
        self.dependency = dependency


async def solve_dependencies(
    dependencies: List[Tuple[str, Callable[..., Any]]],
    overrides: List[Dict[Callable[..., Any], Callable[..., Any]]],
    request: Request | None = None,
) -> tuple[dict[str, Any], list[Tuple[Callable[[], Any], bool]]]:
    """Resolve *dependencies* applying override mappings.

    ``request`` is passed to dependency callables that expect a ``Request``
    argument.  Returns a tuple of ``(values, cleanup)`` where ``values`` maps
    parameter names to resolved values and ``cleanup`` contains callables
    executed after the request to tear down context managers or generators.
    """

    cache: Dict[Callable[..., Any], Any] = {}
    cleanup: list[Tuple[Callable[[], Any], bool]] = []

    async def resolve(fn: Callable[..., Any]) -> Any:
        actual = fn
        for mapping in overrides:
            if fn in mapping:
                actual = mapping[fn]
        if actual in cache:
            return cache[actual]
        sig = inspect.signature(actual)
        kwargs: dict[str, Any] = {}
        for param in sig.parameters.values():
            if param.name == "request" or (
                param.annotation is Request
                or (isinstance(param.annotation, str) and param.annotation == "Request")
            ):
                kwargs[param.name] = request
                continue
            default = param.default
            if isinstance(default, Depends):
                kwargs[param.name] = await resolve(default.dependency)
        result = actual(**kwargs)
        if inspect.isawaitable(result):
            result = await cast(Awaitable[Any], result)
        elif inspect.isasyncgen(result):
            gen = cast(Any, result)
            value = await gen.__anext__()
            cleanup.append((gen.aclose, True))
            result = value
        elif inspect.isgenerator(result):
            gen = cast(Any, result)
            value = next(gen)
            cleanup.append((gen.close, False))
            result = value
        elif hasattr(result, "__aenter__") and hasattr(result, "__aexit__"):
            cm = result
            value = await cast(Awaitable[Any], cm.__aenter__())

            async def _async_exit(cm: Any = cm) -> Any:
                return await cm.__aexit__(None, None, None)

            cleanup.append((_async_exit, True))
            result = value
        elif hasattr(result, "__enter__") and hasattr(result, "__exit__"):
            cm = result
            value = cm.__enter__()
            
            def _sync_exit(cm: Any = cm) -> None:
                cm.__exit__(None, None, None)

            cleanup.append((_sync_exit, False))
            result = value
        cache[actual] = result
        return result

    values = {name: await resolve(dep) for name, dep in dependencies}
    return values, cleanup


class BackgroundTask:
    """Run *func* after the response is sent."""

    def __init__(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.is_async = inspect.iscoroutinefunction(func)

    async def __call__(self) -> None:
        try:
            if self.is_async:
                await self.func(*self.args, **self.kwargs)
            else:
                await asyncio.to_thread(self.func, *self.args, **self.kwargs)
        except Exception:
            logging.getLogger("forzium").error(
                "Background task %s raised an exception",
                getattr(self.func, "__qualname__", repr(self.func)),
                exc_info=True,
            )


class BackgroundTasks:
    """Collection of background tasks."""

    def __init__(
        self,
        tasks: list[BackgroundTask] | None = None,
        queue: Any | None = None,
    ) -> None:
        self.tasks = list(tasks) if tasks else []
        self.queue = queue

    def add_task(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self.queue is not None:
            self.queue.enqueue(func, *args, **kwargs)
        else:
            self.tasks.append(BackgroundTask(func, *args, **kwargs))

    async def __call__(self) -> None:
        for task in self.tasks:
            try:
                await task()
            except Exception:
                logging.getLogger("forzium").error(
                    "Background task %r raised an exception",
                    task,
                    exc_info=True,
                )


class Response:
    """HTTP response container with header and cookie management."""

    def __init__(
        self,
        content: str | bytes = b"",
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
    ) -> None:
        if isinstance(content, str):
            self.body = content.encode()
            default_type = "text/plain; charset=utf-8"
        else:
            self.body = content
            default_type = "application/octet-stream"
        self.status_code = status_code
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.media_type = media_type or default_type
        self.headers.setdefault("content-type", self.media_type)
        self._cookies: SimpleCookie = SimpleCookie()
        self.background = background

    def set_header(self, key: str, value: str) -> None:
        """Set or replace a header."""
        self.headers[key.lower()] = value

    def set_cookie(self, key: str, value: str, **params: Any) -> None:
        """Attach a cookie to the response."""
        self._cookies[key] = value
        for k, v in params.items():
            self._cookies[key][k.replace("_", "-")] = str(v)

    def serialize(self) -> tuple[int, bytes, dict[str, str]]:
        """Return ``(status_code, body, headers)`` for transmission."""
        headers = self.headers.copy()
        if self._cookies:
            headers["set-cookie"] = self._cookies.output(
                header="",
                sep="; ",
            ).strip()
        return self.status_code, self.body, headers

    async def run_background(self) -> None:
        """Execute any attached background task."""
        if self.background is not None:
            await self.background()


__all__ = [
    "BackgroundTask",
    "BackgroundTasks",
    "Depends",
    "Request",
    "Response",
    "solve_dependencies",
]
