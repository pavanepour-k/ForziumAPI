"""Ensure metrics increment and logging middleware hooks work."""

from forzium import ForziumApp
from forzium.middleware import LoggingMiddleware
from infrastructure.monitoring import get_metric


class DummyServer:
    def add_route(self, method: str, path: str, handler):
        self.handler = handler


def test_metrics_and_logging() -> None:
    srv = DummyServer()
    app = ForziumApp(srv)
    logs: list[str] = []
    app.add_middleware(LoggingMiddleware, logger=logs.append)

    @app.get("/a")
    def a() -> dict:
        return {"ok": True}

    route = app.routes[0]
    handler = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    prev = get_metric("requests_total")
    status, body, headers = handler(b"", tuple(), b"")
    assert status == 200 and body
    assert logs == ["request", "response 200"]
    assert get_metric("requests_total") == prev + 1
