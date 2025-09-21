"""Test built-in middleware implementations."""

import base64
import gzip
from pathlib import Path

from forzium import ForziumApp, Request
from forzium.middleware import (
    BaseHTTPMiddleware,
    CORSMiddleware,
    GZipMiddleware,
    HTTPSRedirectMiddleware,
    StaticFilesMiddleware,
    TrustedHostMiddleware,
)


def test_middleware_order_and_short_circuit() -> None:
    app = ForziumApp()
    calls: list[str] = []

    class First(BaseHTTPMiddleware):
        def before_request(  # type: ignore[override]
            self,
            body,
            params,
            query,
        ):
            calls.append("before1")
            return body, params, query, None

        def after_response(  # type: ignore[override]
            self,
            status,
            body,
            headers,
        ):
            calls.append("after1")
            return status, body, headers

    class Second(BaseHTTPMiddleware):
        def before_request(  # type: ignore[override]
            self,
            body,
            params,
            query,
        ):
            calls.append("before2")
            if query == b"stop":
                return body, params, query, (403, "blocked", {})
            return body, params, query, None

        def after_response(  # type: ignore[override]
            self,
            status,
            body,
            headers,
        ):
            calls.append("after2")
            return status, body, headers

    app.add_middleware(First)
    app.add_middleware(Second)

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

    status, body, headers = handler(b"", tuple(), b"")
    assert status == 200
    assert body == "ok"
    assert calls == ["before1", "before2", "handler", "after2", "after1"]

    calls.clear()
    status, body, headers = handler(b"", tuple(), b"stop")
    assert status == 403
    assert body == "blocked"
    assert calls == ["before1", "before2", "after2", "after1"]


def test_cors_middleware() -> None:
    app = ForziumApp()
    app.add_middleware(CORSMiddleware, allow_origin="*")

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
    _, _, headers = handler(b"", tuple(), b"")
    assert headers["access-control-allow-origin"] == "*"


def test_gzip_middleware() -> None:
    app = ForziumApp()
    app.add_middleware(GZipMiddleware)

    @app.get("/g")
    def g() -> str:
        return "data"

    route = app.routes[0]
    handler = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
    )
    _, body, headers = handler(b"", tuple(), b"")
    assert headers["content-encoding"] == "gzip"
    assert gzip.decompress(body.encode("latin1")) == b"data"


def test_https_redirect_middleware() -> None:
    app = ForziumApp()
    calls: list[str] = []
    app.add_middleware(HTTPSRedirectMiddleware)

    @app.get("/r")
    def r() -> str:
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
    status, _, headers = handler(b"", tuple(), b"url=http://example.com/r")
    assert status == 307
    assert headers["location"] == "https://example.com/r"
    assert calls == []


def test_trusted_host_middleware() -> None:
    app = ForziumApp()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["good.com"])

    @app.get("/h")
    def h() -> str:
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
    status, _, _ = handler(b"", tuple(), b"host=bad.com")
    assert status == 400
    status, body, _ = handler(b"", tuple(), b"host=good.com")
    assert status == 200
    assert body == "ok"


def test_static_files_middleware(tmp_path: Path) -> None:
    root = tmp_path
    (root / "hello.txt").write_text("hello")
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAF/gL+X0VdkgAAAABJRU5ErkJggg=="
    )
    (root / "tiny.png").write_bytes(png_data)
    app = ForziumApp()
    calls: list[str] = []

    @app.get("/{path:path}")
    def catch_all(request: Request, path: str) -> str:
        calls.append("handler")
        return "dynamic"

    app.add_middleware(StaticFilesMiddleware, directory=str(root), prefix="/static")

    route = app.routes[0]
    handler = app._make_handler(
        route["func"],
        route["param_names"],
        route["param_converters"],
        route["query_params"],
        route["expects_body"],
        route["dependencies"],
        route.get("expects_request", False),
        route["method"],
        route["path"],
    )

    status, body, headers = handler(b"", ("static/hello.txt",), b"")
    assert status == 200
    assert body == b"hello"
    assert headers["content-type"] == "text/plain"
    assert headers["content-length"] == str(len(body))
    assert calls == []

    status, image_body, image_headers = handler(b"", ("static/tiny.png",), b"")
    assert status == 200
    assert image_body == png_data
    assert image_headers["content-type"] == "image/png"
    assert image_headers["content-length"] == str(len(png_data))
    assert calls == []

    status, _, _ = handler(b"", ("static/missing.txt",), b"")
    assert status == 404
    assert calls == []