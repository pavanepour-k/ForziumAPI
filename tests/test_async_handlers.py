import asyncio
import json

from forzium import ForziumApp
from forzium.responses import HTTPException


def test_async_route_handler() -> None:
    app = ForziumApp()

    @app.get("/async")
    async def async_route() -> dict[str, str]:
        await asyncio.sleep(0)
        return {"hello": "world"}

    route = app.routes[0]
    handler = app._make_handler(  # pylint: disable=protected-access
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
        route.get("expects_request", False),
        route["method"],
        route["path"],
        route.get("background_param"),
    )

    status, body, _ = handler(b"", (), b"")
    assert status == 200
    assert json.loads(body) == {"hello": "world"}


def test_async_route_exception() -> None:
    app = ForziumApp()

    @app.get("/fail")
    async def fail() -> dict[str, str]:
        await asyncio.sleep(0)
        raise HTTPException(418, "nope")

    route = app.routes[0]
    handler = app._make_handler(  # pylint: disable=protected-access
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
        route.get("expects_request", False),
        route["method"],
        route["path"],
        route.get("background_param"),
    )

    status, body, _ = handler(b"", (), b"")
    assert status == 418
    assert json.loads(body) == {"detail": "nope"}