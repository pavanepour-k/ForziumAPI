"""Tests for the rate limiting middleware."""

from __future__ import annotations

import logging
import math

import pytest

from forzium import ForziumApp, RateLimitMiddleware, TestClient
from infrastructure.monitoring import get_metric


class ManualClock:
    """Deterministic monotonic timer for rate limit tests."""

    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


def test_rate_limit_blocks_when_threshold_reached() -> None:
    clock = ManualClock()
    app = ForziumApp()
    app.middleware("http")(RateLimitMiddleware(limit=2, window=1.0, timer=clock, per_client=False))

    @app.get("/limited")
    def limited() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/limited")
    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == "2"
    assert response.headers["x-ratelimit-remaining"] == "1"

    clock.advance(0.1)
    response = client.get("/limited")
    assert response.status_code == 200
    assert response.headers["x-ratelimit-remaining"] == "0"

    clock.advance(0.1)
    response = client.get("/limited")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    assert response.headers["x-ratelimit-remaining"] == "0"

    clock.value = 1.5
    response = client.get("/limited")
    assert response.status_code == 200
    assert response.headers["x-ratelimit-remaining"] == "1"


def test_rate_limit_isolated_per_client() -> None:
    clock = ManualClock()
    app = ForziumApp()
    app.middleware("http")(RateLimitMiddleware(limit=1, window=5.0, timer=clock, per_client=True))

    @app.get("/resource")
    def resource() -> dict[str, str]:
        return {"value": "ok"}

    client = TestClient(app)

    headers_a = {"X-Forwarded-For": "1.1.1.1"}
    headers_b = {"X-Forwarded-For": "2.2.2.2"}

    response = client.get("/resource", headers=headers_a)
    assert response.status_code == 200
    assert response.headers["x-ratelimit-remaining"] == "0"

    response = client.get("/resource", headers=headers_a)
    assert response.status_code == 429

    response = client.get("/resource", headers=headers_b)
    assert response.status_code == 200


def test_rate_limit_configured_via_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure environment-driven configuration attaches the middleware automatically.
    monkeypatch.setenv("FORZIUM_RATE_LIMIT", "1")
    monkeypatch.setenv("FORZIUM_RATE_LIMIT_WINDOW", "10")
    monkeypatch.setenv("FORZIUM_RATE_LIMIT_SCOPE", "global")

    app = ForziumApp()

    @app.get("/auto")
    def auto() -> dict[str, str]:
        return {"auto": "configured"}

    client = TestClient(app)
    first = client.get("/auto")
    second = client.get("/auto")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"].isdigit()


def test_retry_after_header_matches_remaining_window() -> None:
    clock = ManualClock()
    app = ForziumApp()
    app.middleware("http")(RateLimitMiddleware(limit=1, window=2.5, timer=clock, per_client=False))

    @app.get("/window")
    def window_handler() -> dict[str, str]:
        return {"window": "open"}

    client = TestClient(app)

    initial = client.get("/window")
    assert initial.status_code == 200
    assert initial.headers["x-ratelimit-reset"] == str(math.ceil(2.5))

    clock.advance(0.7)
    blocked = client.get("/window")
    expected_retry_after = math.ceil(2.5 - 0.7)
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == str(expected_retry_after)
    assert blocked.headers["x-ratelimit-reset"] == str(expected_retry_after)
    assert blocked.headers["retry-after"].isdigit()
    assert blocked.text == "{\"detail\": \"Too Many Requests\"}"

    clock.advance(2.0)
    recovered = client.get("/window")
    assert recovered.status_code == 200


def test_rate_limit_path_scope_isolation() -> None:
    clock = ManualClock()
    app = ForziumApp()
    limiter = RateLimitMiddleware(
        limit=1,
        window=5.0,
        timer=clock,
        per_client=False,
        include_path=True,
    )
    app.middleware("http")(limiter)

    @app.get("/alpha")
    def alpha() -> dict[str, str]:
        return {"route": "alpha"}

    @app.get("/beta")
    def beta() -> dict[str, str]:
        return {"route": "beta"}

    client = TestClient(app)

    first_alpha = client.get("/alpha")
    assert first_alpha.status_code == 200

    second_alpha = client.get("/alpha")
    assert second_alpha.status_code == 429
    assert second_alpha.headers["retry-after"].isdigit()

    beta_response = client.get("/beta")
    assert beta_response.status_code == 200
    assert beta_response.headers["x-ratelimit-remaining"] == "0"


def test_user_scope_configured_via_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORZIUM_RATE_LIMIT", "1")
    monkeypatch.setenv("FORZIUM_RATE_LIMIT_WINDOW", "10")
    monkeypatch.setenv("FORZIUM_RATE_LIMIT_SCOPE", "user")
    monkeypatch.setenv("FORZIUM_RATE_LIMIT_IDENTIFIER_HEADER", "X-Tenant-ID")

    app = ForziumApp()

    @app.get("/tenant")
    def tenant_handler() -> dict[str, str]:
        return {"tenant": "ok"}

    client = TestClient(app)

    tenant_a = {"X-Tenant-ID": "tenant-a"}
    tenant_b = {"X-Tenant-ID": "tenant-b"}

    first = client.get("/tenant", headers=tenant_a)
    assert first.status_code == 200

    second = client.get("/tenant", headers=tenant_a)
    assert second.status_code == 429
    assert second.headers["retry-after"].isdigit()

    third = client.get("/tenant", headers=tenant_b)
    assert third.status_code == 200
    assert third.headers["x-ratelimit-remaining"] == "0"


def test_rate_limit_emits_warning_and_metric(caplog: pytest.LogCaptureFixture) -> None:
    clock = ManualClock()
    app = ForziumApp()
    limiter = RateLimitMiddleware(
        limit=1,
        window=1.0,
        timer=clock,
        per_client=True,
    )
    app.middleware("http")(limiter)

    @app.get("/warn")
    def warn_handler() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    headers = {"X-Forwarded-For": "5.5.5.5"}
    baseline = get_metric("requests_rate_limited_total")

    with caplog.at_level(logging.WARNING, logger="forzium"):
        client.get("/warn", headers=headers)
        caplog.clear()
        blocked = client.get("/warn", headers=headers)

    assert blocked.status_code == 429
    assert get_metric("requests_rate_limited_total") == baseline + 1.0

    messages = "\n".join(record.message for record in caplog.records)
    assert "rate_limit.blocked" in messages
    assert '"client":"5.5.5.5"' in messages
    assert '"path":"/warn"' in messages