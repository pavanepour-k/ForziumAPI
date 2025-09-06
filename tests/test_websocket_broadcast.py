"""Tests for WebSocket broadcast channels."""

import asyncio

from forzium.websockets import BroadcastChannel, WebSocket


def test_broadcast_channel() -> None:
    chan = BroadcastChannel()
    w1, w2 = WebSocket(), WebSocket()
    asyncio.run(chan.connect(w1))
    asyncio.run(chan.connect(w2))
    asyncio.run(chan.broadcast("hi"))
    assert w1.sent == ["hi"] and w2.sent == ["hi"]
    asyncio.run(chan.disconnect(w1))
    asyncio.run(chan.broadcast("bye"))
    assert w1.sent == ["hi"] and w2.sent == ["hi", "bye"]
