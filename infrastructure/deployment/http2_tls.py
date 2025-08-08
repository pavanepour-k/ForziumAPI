"""Minimal TLS server capable of handling concurrent requests."""

from __future__ import annotations

import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


class _Handler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    def do_GET(self) -> None:  # pragma: no cover - exercised via tests
        body = self.server.app(self.path)  # type: ignore[attr-defined]
        data = body.encode()
        self.send_response(200)
        self.send_header("content-type", "text/plain")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def run(
    app: Callable[[str], str], host: str, port: int, certfile: str, keyfile: str
) -> ThreadingHTTPServer:
    """Run `app` on a TLS-enabled server and return the server instance."""
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.app = app  # type: ignore[attr-defined]
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile, keyfile)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


__all__ = ["run"]
