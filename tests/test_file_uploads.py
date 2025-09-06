"""Verify multipart form parsing and file handling."""

import asyncio

from forzium import ForziumApp, Request
from forzium.responses import StreamingResponse
from forzium.testclient import TestClient


def test_multipart_form() -> None:
    app = ForziumApp()

    @app.post("/upload")
    def upload(request: Request):
        form = asyncio.run(request.form())
        file = request.files["file"]
        return {
            "field": form["field"],
            "filename": file["filename"],
            "content": file["content"].decode(),
        }

    client = TestClient(app)
    boundary = "boundary"  # simple fixed boundary
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="field"\r\n\r\n'
        "value\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; '
        'filename="test.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "hello\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    resp = client.request("POST", "/upload", body=body)
    assert resp.json() == {
        "field": "value",
        "filename": "test.txt",
        "content": "hello",
    }


def test_streaming_response() -> None:
    app = ForziumApp()

    chunks: list[bytes] = []

    def gen():
        for part in [b"a", b"b", b"c"]:
            chunks.append(part)
            yield part

    @app.get("/stream")
    def stream():
        return StreamingResponse(gen())

    client = TestClient(app)
    resp = client.get("/stream")
    assert resp.text == "abc"
    assert chunks == [b"a", b"b", b"c"]
