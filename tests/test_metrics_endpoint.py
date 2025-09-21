"""Ensure Prometheus metrics endpoint exposes recorded metrics."""

from forzium import ForziumApp, TestClient


def _parse_metrics(payload: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in payload.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " " not in line:
            continue
        key, value = line.split(" ", 1)
        try:
            metrics[key] = float(value)
        except ValueError:
            continue
    return metrics


def test_metrics_endpoint() -> None:
    app = ForziumApp()

    @app.get("/ping")
    def ping() -> str:
        return "pong"

    client = TestClient(app)
    client.get("/ping")
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    content_type = metrics_response.headers.get("content-type", "")
    assert content_type.startswith("text/plain; version=0.0.4")
    metrics = _parse_metrics(metrics_response.text)
    assert "requests_total" in metrics
    assert metrics["requests_total"] >= 1.0