from forzium import ForziumApp
from infrastructure.monitoring import get_metric


def test_websocket_metric_increment() -> None:
    app = ForziumApp()

    @app.websocket("/ws")
    async def ws_handler(ws):
        await ws.send_text("hi")

    route = app.ws_routes[0]
    handler = app._make_ws_handler(
        route["func"], route["param_names"], route["param_converters"]
    )

    class DummyWS:
        async def send_text(self, text: str) -> None:
            pass

    import asyncio

    asyncio.run(handler(DummyWS(), ()))
    assert get_metric("websocket_connections_total") >= 1