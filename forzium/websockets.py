"""In-memory WebSocket primitives with optional clustering."""

from __future__ import annotations

from typing import Any, Callable

from infrastructure.monitoring import start_span


class WebSocket:
    """In-memory stand-in for a WebSocket connection."""

    def __init__(
        self, on_close: Callable[["WebSocket"], Any] | None = None
    ) -> None:
        self.accepted = False
        self.sent: list[str] = []
        self.received: list[str] = []
        self.closed = False
        self._close_callbacks: list[Callable[["WebSocket"], Any]] = []
        if on_close is not None:
            self._close_callbacks.append(on_close)

    def add_close_callback(
        self, callback: Callable[["WebSocket"], Any]
    ) -> None:
        """Register *callback* to be invoked when closed."""

        self._close_callbacks.append(callback)

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        if not self.received:
            raise RuntimeError("no messages to receive")
        return self.received.pop(0)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for cb in list(self._close_callbacks):
            cb(self)

class WebSocketRoute:
    """Bind a path to a WebSocket endpoint."""

    def __init__(self, path: str, endpoint: Callable[..., Any]) -> None:
        self.path = path
        self.endpoint = endpoint


__all__ = ["WebSocket", "WebSocketRoute"]


class BroadcastChannel:
    """Manage WebSocket connections and broadcast messages."""

    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        self.connections.append(ws)
        ws.add_close_callback(self._remove)

    async def disconnect(self, ws: WebSocket) -> None:
        await ws.close()

    def _remove(self, ws: WebSocket) -> None:
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: str) -> None:
        for ws in list(self.connections):
            await ws.send_text(message)


class ClusteredBroadcastChannel(BroadcastChannel):
    """Broadcast messages across channel instances in a cluster."""

    _clusters: dict[str, list["ClusteredBroadcastChannel"]] = {}

    def __init__(self, cluster: str = "default") -> None:
        super().__init__()
        self.cluster = cluster
        self._clusters.setdefault(cluster, []).append(self)

    async def broadcast(self, message: str) -> None:
        span_name = f"cluster.broadcast:{self.cluster}"
        with start_span(span_name):
            for chan in list(self._clusters.get(self.cluster, [])):
                for ws in list(chan.connections):
                    await ws.send_text(message)


__all__.extend(["BroadcastChannel", "ClusteredBroadcastChannel"])


class WebSocketServer(BroadcastChannel):
    """Simple in-memory server handling multiple WebSocket clients."""

    async def connect(self) -> WebSocket:
        """Create a WebSocket and register it with the server."""

        ws = WebSocket()
        await super().connect(ws)
        return ws


__all__.append("WebSocketServer")
