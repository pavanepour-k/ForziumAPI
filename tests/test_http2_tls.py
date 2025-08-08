"""Test TLS server handling concurrent streams."""

import ssl
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

from infrastructure.deployment import http2_tls


def _generate_cert(tmp: Path) -> tuple[str, str]:
    cert = tmp / "cert.pem"
    key = tmp / "key.pem"
    cmd = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-subj",
        "/CN=localhost",
        "-keyout",
        str(key),
        "-out",
        str(cert),
        "-days",
        "1",
    ]
    subprocess.run(
        cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return str(cert), str(key)


def test_http2_tls_concurrent_requests() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cert, key = _generate_cert(Path(tmpdir))

        def app(path: str) -> str:
            time.sleep(0.1)
            return "ok"

        srv = http2_tls.run(app, "127.0.0.1", 8443, cert, key)
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            url = "https://127.0.0.1:8443/"
            start = time.time()
            with ThreadPoolExecutor() as pool:
                futs = [pool.submit(urlopen, url, context=ctx) for _ in range(2)]
                bodies = [f.result().read() for f in futs]
            duration = time.time() - start
            assert bodies == [b"ok", b"ok"]
            assert duration < 0.2
        finally:
            srv.shutdown()
