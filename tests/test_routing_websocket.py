"""Validate routing verbs, typed params, mounts, and websockets."""

import asyncio

from forzium.app import ForziumApp
from forzium.websockets import WebSocket


def test_http_verbs_and_typed_params() -> None:
    app = ForziumApp()

    @app.get("/items/{num:int}")
    def read(num: int) -> dict[str, int]:
        return {"n": num}

    handler = app._make_handler(
        app.routes[0]["func"],
        app.routes[0]["param_names"],
        app.routes[0]["param_converters"],
        app.routes[0]["query_params"],
        app.routes[0]["expects_body"],
        app.routes[0]["dependencies"],
    )
    status, body, headers = handler(b"", ("5",), b"")
    assert status == 200
    assert body == '{"n": 5}'
    assert headers == {}

    verbs = [
        app.post,
        app.put,
        app.delete,
        app.patch,
        app.head,
        app.options,
        app.trace,
    ]
    for idx, verb in enumerate(verbs, 1):

        @verb(f"/v{idx}")
        def _() -> str:
            return "ok"

    methods = {route["method"] for route in app.routes}
    assert methods == {
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "HEAD",
        "OPTIONS",
        "TRACE",
    }


def test_mount_and_lifespan() -> None:
    main = ForziumApp()
    sub = ForziumApp()
    hit: list[str] = []

    @sub.get("/ping")
    def ping() -> str:
        return "pong"

    @sub.on_event("startup")
    def start() -> None:
        hit.append("x")

    main.include_router(sub, prefix="/sub", host="example.com")
    assert main.routes[0]["path"] == "/sub/ping"
    assert main.routes[0]["host"] == "example.com"
    asyncio.run(main.startup())
    assert hit == ["x"]


def test_websocket_route() -> None:
    app = ForziumApp()

    @app.websocket("/ws/{val:int}")
    async def ws(ws: WebSocket, val: int) -> None:
        await ws.accept()
        await ws.send_text(str(val))
        await ws.close()

    client = WebSocket()
    route = app.ws_routes[0]
    handler = app._make_ws_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
    )
    asyncio.run(handler(client, ("7",)))
    assert client.accepted
    assert client.sent == ["7"]
    assert client.closed
