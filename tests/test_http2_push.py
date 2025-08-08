"""Test simulated HTTP/2 server push."""

from forzium import ForziumApp, push


class DummyServer:
    def add_route(self, method: str, path: str, handler):
        self.handler = handler


def test_push_header() -> None:
    srv = DummyServer()
    app = ForziumApp(srv)

    @app.get("/")
    def home():
        push("/style.css")
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
    status, body, headers = handler(b"", tuple(), b"")
    assert status == 200
    assert headers["link"] == "</style.css>; rel=preload"
