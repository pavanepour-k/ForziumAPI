from base64 import b64encode

from forzium.auth import (
    HTTPAuthorizationCredentials,
    HTTPBasicCredentials,
    http_basic,
    http_bearer,
)


def test_http_basic_and_bearer_helpers() -> None:
    basic_header = "Basic " + b64encode(b"alice:secret").decode()
    creds = http_basic(basic_header)
    assert isinstance(creds, HTTPBasicCredentials)
    assert creds.username == "alice"
    assert creds.password == "secret"

    bearer = http_bearer("Bearer token123")
    assert isinstance(bearer, HTTPAuthorizationCredentials)
    assert bearer.credentials == "token123"