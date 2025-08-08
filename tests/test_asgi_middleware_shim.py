from forzium import ForziumApp
from forzium.dependency import Request, Response


def test_asgi_middleware_order() -> None:
    app = ForziumApp()
    calls: list[str] = []

    @app.middleware("http")
    def first(req: Request, call_next):  # type: ignore[override]
        calls.append("before1")
        resp = call_next(req)
        calls.append("after1")
        return resp

    @app.middleware("http")
    def second(req: Request, call_next):  # type: ignore[override]
        calls.append("before2")
        resp = call_next(req)
        calls.append("after2")
        return resp

    @app.get("/hi")
    def hi() -> str:
        calls.append("handler")
        return "ok"

    route = app.routes[0]
    handler = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, _ = handler(b"", tuple(), b"")
    assert status == 200
    assert body == "ok"
    assert calls == ["before1", "before2", "handler", "after2", "after1"]


def test_asgi_middleware_short_circuit() -> None:
    app = ForziumApp()

    @app.middleware("http")
    def stop(_: Request, __):  # type: ignore[override]
        return Response("halt", status_code=403)

    @app.get("/x")
    def x() -> str:
        return "ok"

    route = app.routes[0]
    handler = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, _ = handler(b"", tuple(), b"")
    assert status == 403
    assert body == "halt"


def test_async_middleware_support() -> None:
    app = ForziumApp()
    calls: list[str] = []

    @app.middleware("http")
    async def mid(req: Request, call_next):  # type: ignore[override]
        calls.append("before")
        resp = await call_next(req)
        calls.append("after")
        return resp

    @app.get("/a")
    def a() -> str:
        calls.append("handler")
        return "ok"

    route = app.routes[0]
    handler = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    status, body, _ = handler(b"", tuple(), b"")
    assert status == 200
    assert body == "ok"
    assert calls == ["before", "handler", "after"]
