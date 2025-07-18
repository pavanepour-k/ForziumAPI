# python/tests/integration/test_rust_response.py
import pytest
from forzium.response import Response
from forzium._rust.response import PyResponseBuilder

def test_rust_response_builder():
    """VERIFY Rust response builder integration."""
    builder = PyResponseBuilder()

    # BUILD JSON response
    builder.status(200)
    builder.header("Content-Type", "application/json")
    builder.json_body({"message": "Hello, Rust!"})

    response = builder.build()
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.is_json()

    # BUILD text response
    builder = PyResponseBuilder()
    builder.status(201)
    builder.text_body("Plain text response")

    response = builder.build()
    assert response.is_text()
    assert response.body_string() == "Plain text response"
