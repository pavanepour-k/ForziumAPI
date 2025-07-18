from typing import Dict, Any

class PyResponseBuilder:
    """Stub for Rust PyResponseBuilder."""
    def __init__(self):
        self._status = 200
        self._headers = {}
        self._body = None

    def status(self, code: int):
        self._status = code
        return self

    def header(self, key: str, value: str):
        self._headers[key] = value
        return self

    def json_body(self, data: Dict[str, Any]):
        # Set JSON content type and body as JSON string
        self._headers["Content-Type"] = "application/json"
        import json
        self._body = json.dumps(data)
        return self

    def text_body(self, text: str):
        # Set text content type and body
        self._headers["Content-Type"] = "text/plain"
        self._body = text
        return self

    def build(self):
        from forzium.response import Response
        resp = Response(
            status_code=self._status,
            headers=self._headers.copy(),
            body=self._body
        )
        return resp
