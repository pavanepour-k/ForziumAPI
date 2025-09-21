"""Test dependency injection in Forzium."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from forzium import ForziumApp, TestClient
from forzium.dependency import Depends
from infrastructure import monitoring


def provide_token() -> str:
    return "abc"


def test_dependency_injection() -> None:
    app = ForziumApp()

    @app.get("/token")
    def handler(token: str = Depends(provide_token)) -> dict[str, str]:
        return {"token": token}

    route = app.routes[0]
    handler_fn = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert body == '{"token": "abc"}'
    assert headers == {}


async def provide_async() -> str:
    await asyncio.sleep(0)
    return "async"


def test_async_dependency_injection() -> None:
    app = ForziumApp()

    @app.get("/async")
    def handler(token: str = Depends(provide_async)) -> dict[str, str]:
        return {"token": token}

    route = app.routes[0]
    handler_fn = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert body == '{"token": "async"}'
    assert headers == {}


def test_context_manager_dependency_injection() -> None:
    called: list[str] = []

    @contextmanager
    def provide_cm() -> str:
        called.append("enter")
        try:
            yield "cm"
        finally:
            called.append("exit")

    app = ForziumApp()

    @app.get("/cm")
    def handler(token: str = Depends(provide_cm)) -> dict[str, str]:
        return {"token": token}

    route = app.routes[0]
    handler_fn = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert body == '{"token": "cm"}'
    assert headers == {}
    assert called == ["enter", "exit"]


def test_async_context_manager_dependency_injection() -> None:
    called: list[str] = []

    @asynccontextmanager
    async def provide_acm() -> str:
        called.append("enter")
        try:
            yield "acm"
        finally:
            called.append("exit")

    app = ForziumApp()

    @app.get("/acm")
    def handler(token: str = Depends(provide_acm)) -> dict[str, str]:
        return {"token": token}

    route = app.routes[0]
    handler_fn = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert body == '{"token": "acm"}'
    assert headers == {}
    assert called == ["enter", "exit"]


def test_dependency_overrides() -> None:
    """App overrides should trump router overrides."""

    router = ForziumApp()

    @router.get("/token")
    def handler(token: str = Depends(provide_token)) -> dict[str, str]:
        return {"token": token}

    router.dependency_overrides[provide_token] = lambda: "router"

    app = ForziumApp()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    resp = client.get("/api/token")
    assert resp.json() == {"token": "router"}

    app.dependency_overrides[provide_token] = lambda: "app"
    resp = client.get("/api/token")
    assert resp.json() == {"token": "app"}


def test_nested_dependencies() -> None:
    def get_token() -> str:
        return "inner"

    def wrap(token: str = Depends(get_token)) -> str:
        return f"wrapped:{token}"

    app = ForziumApp()

    @app.get("/nested")
    def handler(value: str = Depends(wrap)) -> dict[str, str]:
        return {"token": value}

    client = TestClient(app)
    resp = client.get("/nested")
    assert resp.json() == {"token": "wrapped:inner"}


def test_yield_dependencies() -> None:
    called: list[str] = []

    def gen_dep() -> Any:
        called.append("enter")
        try:
            yield "gen"
        finally:
            called.append("exit")

    app = ForziumApp()

    @app.get("/gen")
    def handler(token: str = Depends(gen_dep)) -> dict[str, str]:
        return {"token": token}

    route = app.routes[0]
    handler_fn = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert body == '{"token": "gen"}'
    assert headers == {}
    assert called == ["enter", "exit"]


def test_dependency_runtime_error_triggers_internal_error_and_finalizer() -> None:
    app = ForziumApp()
    payloads: list[dict[str, Any]] = []

    def recorder(payload: dict[str, Any]) -> None:
        payloads.append(payload)

    monitoring.reset_telemetry_finalizer_counters()
    monitoring.register_telemetry_finalizer(recorder)
    try:
        def fail_dependency() -> str:
            raise RuntimeError("dep exploded")

        @app.get("/boom")
        def boom_route(value: str = Depends(fail_dependency)) -> dict[str, str]:
            return {"value": value}

        client = TestClient(app)
        response = client.get("/boom")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal Server Error"}

        assert monitoring.get_telemetry_finalizer_invocations() == 1
        assert len(payloads) == 1
        payload = payloads[0]
        assert payload["route"] == "/boom"
        assert payload["status_code"] == 500
        assert payload["error"] is True
    finally:
        monitoring.unregister_telemetry_finalizer(recorder)
        monitoring.reset_telemetry_finalizer_counters()


def test_async_yield_dependencies() -> None:
    called: list[str] = []

    async def agen_dep() -> Any:
        called.append("enter")
        try:
            yield "agen"
        finally:
            called.append("exit")

    app = ForziumApp()

    @app.get("/agen")
    def handler(token: str = Depends(agen_dep)) -> dict[str, str]:
        return {"token": token}

    route = app.routes[0]
    handler_fn = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, headers = handler_fn(b"", tuple(), b"")
    assert status == 200
    assert body == '{"token": "agen"}'
    assert headers == {}
    assert called == ["enter", "exit"]