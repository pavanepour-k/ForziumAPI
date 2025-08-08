"""Tests for clustered WebSocket broadcast."""

import asyncio

from infrastructure.monitoring import get_traces
from forzium.websockets import ClusteredBroadcastChannel, WebSocket


def test_cluster_broadcast() -> None:
    c1 = ClusteredBroadcastChannel("g")
    c2 = ClusteredBroadcastChannel("g")
    w1, w2 = WebSocket(), WebSocket()
    asyncio.run(c1.connect(w1))
    asyncio.run(c2.connect(w2))
    asyncio.run(c1.broadcast("hi"))
    names = [t if isinstance(t, str) else getattr(t, "name", "") for t in get_traces()]
    assert "cluster.broadcast:g" in names
    assert w1.sent == ["hi"] and w2.sent == ["hi"]
