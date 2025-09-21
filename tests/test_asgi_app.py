"""Validate minimal ASGI application features."""

import asyncio

from forzium.asgi import ASGIApp


def run(coro):
    """Synchronously execute an async coroutine.

    ``asyncio.get_event_loop().run_until_complete`` is deprecated for implicit
    loop creation starting with Python 3.12. ``asyncio.run`` handles loop
    lifecycle safely and avoids DeprecationWarnings in the test suite.
    """

    return asyncio.run(coro)


def test_lifespan_events() -> None:
    app = ASGIApp()
    events: list[str] = []

    @app.on_event("startup")
    def _startup() -> None:
        events.append("up")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        events.append("down")

    messages = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ]

    async def receive() -> dict:
        return messages.pop(0)

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    run(app({"type": "lifespan"}, receive, send))

    assert events == ["up", "down"]
    assert sent == [
        {"type": "lifespan.startup.complete"},
        {"type": "lifespan.shutdown.complete"},
    ]


def test_http_route() -> None:
    app = ASGIApp()

    @app.route("/hello", "GET")
    def hello() -> str:
        return "hi"

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {"type": "http", "path": "/hello", "method": "GET"}
    run(app(scope, receive, send))

    assert sent[0]["status"] == 200
    assert sent[1]["body"] == b"hi"
