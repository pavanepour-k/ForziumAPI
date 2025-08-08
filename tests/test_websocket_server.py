"""End-to-end tests for the in-memory WebSocket server."""

import asyncio

from forzium.websockets import WebSocketServer


def test_server_broadcast_and_close() -> None:
    server = WebSocketServer()
    w1 = asyncio.run(server.connect())
    w2 = asyncio.run(server.connect())
    asyncio.run(server.broadcast("hi"))
    assert w1.sent == ["hi"] and w2.sent == ["hi"]
    asyncio.run(w1.close())
    assert w1.closed and len(server.connections) == 1
    asyncio.run(server.broadcast("bye"))
    assert w1.sent == ["hi"]
    assert w2.sent == ["hi", "bye"]
