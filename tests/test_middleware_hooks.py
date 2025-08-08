"""Ensure request and response middleware execute."""

from forzium import ForziumApp


class DummyServer:
    """Record the last handler added via ``add_route``."""

    def add_route(self, method: str, path: str, handler) -> None:
        self.handler = handler


def test_request_response_hooks() -> None:
    """Both request and response hooks run for each call."""
    srv = DummyServer()
    app = ForziumApp(srv)
    calls: list[str] = []

    def req(body: bytes, params: tuple, query: bytes):
        calls.append("req")
        return body, params, query

    def resp(status: int, body: str):
        calls.append("resp")
        return status, body

    app.add_request_middleware(req)
    app.add_response_middleware(resp)

    @app.get("/hello")
    def hello() -> dict:
        return {"msg": "hi"}

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
    assert body == '{"msg": "hi"}'
    assert headers == {}
    assert calls == ["req", "resp"]
