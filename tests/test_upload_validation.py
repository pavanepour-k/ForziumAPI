"""Validate file upload limits and MIME checks."""

import asyncio

from forzium import ForziumApp, Request
from forzium.testclient import TestClient


def _build_body(boundary: str, content: str, content_type: str = "text/plain") -> bytes:
    return (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--\r\n"
    ).encode()


def test_file_upload_limits_and_mime() -> None:
    app = ForziumApp(max_upload_size=5, allowed_mime_types={"text/plain"})

    @app.post("/upload")
    def upload(request: Request):
        asyncio.run(request.form())
        return {"ok": True}

    client = TestClient(app)
    boundary = "boundary"

    body = _build_body(boundary, "hello", "text/plain")
    resp = client.request("POST", "/upload", body=body)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    big_body = _build_body(boundary, "toolarge", "text/plain")
    resp2 = client.request("POST", "/upload", body=big_body)
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "file too large"

    bad_mime = _build_body(boundary, "hi", "application/json")
    resp3 = client.request("POST", "/upload", body=bad_mime)
    assert resp3.status_code == 400
    assert resp3.json()["detail"] == "unsupported media type"