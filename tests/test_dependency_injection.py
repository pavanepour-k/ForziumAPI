"""Test dependency injection in Forzium."""

import asyncio
from contextlib import asynccontextmanager, contextmanager

from forzium import ForziumApp, TestClient
from forzium.dependency import Depends


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