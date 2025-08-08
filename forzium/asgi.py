"""Minimal ASGI application with lifecycle hooks.

Provides a tiny Starlette-like interface with route registration and
startup/shutdown events. This forms the foundation for replacing the
Starlette dependency.
"""

from __future__ import annotations

import inspect
from typing import Awaitable, Callable, Dict, List, Tuple

Scope = Dict[str, object]
Receive = Callable[[], Awaitable[Dict[str, object]]]
Send = Callable[[Dict[str, object]], Awaitable[None]]
Handler = Callable[[], Awaitable[bytes | str] | bytes | str]
EventHandler = Callable[[], Awaitable[None] | None]


class ASGIApp:
    """Basic ASGI app supporting routes and lifespan events."""

    def __init__(self) -> None:
        self._routes: Dict[Tuple[str, str], Handler] = {}
        self._startup: List[EventHandler] = []
        self._shutdown: List[EventHandler] = []

    def route(self, path: str, method: str = "GET") -> Callable[[Handler], Handler]:
        """Register *handler* for HTTP *method* and *path*."""

        def decorator(func: Handler) -> Handler:
            self._routes[(path, method.upper())] = func
            return func

        return decorator

    def on_event(self, event: str) -> Callable[[EventHandler], EventHandler]:
        """Register a startup or shutdown handler."""
        collection = self._startup if event == "startup" else self._shutdown

        def decorator(func: EventHandler) -> EventHandler:
            collection.append(func)
            return func

        return decorator

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Dispatch ASGI *scope* to handlers."""
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        else:
            raise NotImplementedError(f"Unsupported scope type {scope['type']}")

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        await receive()  # lifespan.startup
        for func in self._startup:
            result = func()
            if inspect.iscoroutine(result):
                await result
        await send({"type": "lifespan.startup.complete"})
        await receive()  # lifespan.shutdown
        for func in self._shutdown:
            result = func()
            if inspect.iscoroutine(result):
                await result
        await send({"type": "lifespan.shutdown.complete"})

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))
        handler = self._routes.get((path, method))
        if handler is None:
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        await receive()  # discard request body
        result = handler()
        if inspect.iscoroutine(result):
            result = await result
        body = result.encode() if isinstance(result, str) else result
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": body})


__all__ = ["ASGIApp"]
