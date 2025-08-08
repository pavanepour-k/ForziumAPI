"""Ensure Prometheus metrics endpoint exposes recorded metrics."""

from forzium.app import ForziumApp


def test_metrics_endpoint() -> None:
    app = ForziumApp()

    @app.get("/ping")
    def ping() -> str:
        return "pong"

    route_ping = app.routes[0]
    handler_ping = app._make_handler(
        route_ping["func"],
        route_ping["param_names"],
        route_ping["param_converters"],
        route_ping["query_params"],
        route_ping["expects_body"],
        route_ping["dependencies"],
    )
    handler_ping(b"", (), b"")
    route_metrics = next(r for r in app.routes if r["path"] == "/metrics")
    handler_metrics = app._make_handler(
        route_metrics["func"],
        route_metrics["param_names"],
        route_metrics["param_converters"],
        route_metrics["query_params"],
        route_metrics["expects_body"],
        route_metrics["dependencies"],
    )
    status, body, _ = handler_metrics(b"", (), b"")
    assert status == 200
    assert "requests_total" in body
