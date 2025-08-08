"""Validate Request and Response header/cookie handling."""

import asyncio
import json
from typing import Any, Iterable

import pytest

from forzium.http import (
    BackgroundTask,
    FileResponse,
    HTMLResponse,
    HTTPException,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Request,
    Response,
    StreamingResponse,
)


def test_request_parses_headers_and_cookies() -> None:
    req = Request(headers={"Content-Type": "application/json", "Cookie": "a=1; b=2"})
    assert req.headers["content-type"] == "application/json"
    assert req.cookies["a"] == "1"
    assert req.cookies["b"] == "2"


def test_request_helpers() -> None:
    req = Request(
        method="post",
        url="/path?x=1",
        body=b"a=1&b=2",
        path_params={"id": "42"},
    )

    async def gather() -> list[bytes]:
        chunks: list[bytes] = []
        async for chunk in req.stream():
            chunks.append(chunk)
        return chunks

    assert req.method == "POST"
    assert req.url == "/path?x=1"
    assert req.query_params == {"x": "1"}
    assert req.path_params == {"id": "42"}
    assert asyncio.run(req.body()) == b"a=1&b=2"
    assert asyncio.run(req.form()) == {"a": "1", "b": "2"}
    assert asyncio.run(gather()) == [b"a=1&b=2"]

    req_json = Request(body=json.dumps({"k": 1}).encode())
    assert asyncio.run(req_json.json()) == {"k": 1}


def test_response_serializes_headers_and_cookies() -> None:
    resp = Response("hi", headers={"X-Test": "1"})
    resp.set_cookie("token", "abc", httponly=True)
    status, body, headers = resp.serialize()
    assert status == 200
    assert body == b"hi"
    assert headers["x-test"] == "1"
    assert "token=abc" in headers["set-cookie"]
    assert "httponly" in headers["set-cookie"].lower()


def test_response_media_type_and_headers() -> None:
    resp = Response("hi", media_type="text/plain")
    resp.set_header("X-One", "1")
    status, body, headers = resp.serialize()
    assert status == 200
    assert body == b"hi"
    assert headers["content-type"] == "text/plain"
    assert headers["x-one"] == "1"


def test_response_runs_background_task() -> None:
    hit: list[int] = []

    def mark(num: int) -> None:
        hit.append(num)

    resp = Response(background=BackgroundTask(mark, 1))
    asyncio.run(resp.run_background())
    assert hit == [1]


def test_json_response() -> None:
    resp = JSONResponse({"a": 1})
    status, body, headers = resp.serialize()
    assert status == 200
    assert body == b"{" + b'"a": 1' + b"}"
    assert headers["content-type"] == "application/json"
    with pytest.raises(TypeError):
        JSONResponse(object())


def test_plain_html_and_redirect_responses(tmp_path: Any) -> None:
    text_resp = PlainTextResponse("hi")
    _, body, headers = text_resp.serialize()
    assert body == b"hi"
    assert headers["content-type"].startswith("text/plain")

    html_resp = HTMLResponse("<b>ok</b>")
    _, body, headers = html_resp.serialize()
    assert b"<b>ok" in body
    assert headers["content-type"].startswith("text/html")

    redirect = RedirectResponse("/other")
    status, body, headers = redirect.serialize()
    assert status == 307
    assert body == b""
    assert headers["location"] == "/other"


def test_file_and_streaming_response(tmp_path: Any) -> None:
    file = tmp_path / "f.txt"
    file.write_text("data")
    resp = FileResponse(str(file))
    status, body, headers = resp.serialize()
    assert status == 200
    assert body == b"data"
    assert headers["content-length"] == "4"
    with pytest.raises(FileNotFoundError):
        FileResponse(str(file / "missing"))

    stream = StreamingResponse([b"a", b"b"])
    _, body, _ = stream.serialize()
    assert body == b"ab"

    def bad_gen() -> Iterable[bytes]:
        yield b"ok"
        raise RuntimeError

    with pytest.raises(RuntimeError):
        StreamingResponse(bad_gen()).serialize()


def test_http_exception() -> None:
    exc = HTTPException(404, "x", headers={"a": "b"})
    assert exc.status_code == 404
    assert exc.detail == "x"
    assert exc.headers["a"] == "b"
