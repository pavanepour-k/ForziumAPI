from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
import json
from .._rust import response as _rust_response
from ..exceptions import ValidationError

@dataclass
class Response:
    """HTTP Response wrapper with Rust backend."""
    
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Union[str, bytes, Dict[str, Any]]] = None
    
    def __post_init__(self):
        """VALIDATE response parameters."""
        if not 100 <= self.status_code <= 599:
            raise ValidationError(
                message="Invalid status code",
                field="status_code",
                value=self.status_code
            )
    
    @classmethod
    def json(cls, data: Dict[str, Any], status: int = 200) -> 'Response':
        """CREATE JSON response."""
        return cls(
            status_code=status,
            headers={"Content-Type": "application/json"},
            body=json.dumps(data)
        )
    
    @classmethod
    def text(cls, text: str, status: int = 200) -> 'Response':
        """CREATE text response."""
        return cls(
            status_code=status,
            headers={"Content-Type": "text/plain"},
            body=text
        )
    
    @classmethod
    def binary(cls, data: bytes, status: int = 200) -> 'Response':
        """CREATE binary response."""
        return cls(
            status_code=status,
            headers={"Content-Type": "application/octet-stream"},
            body=data
        )
    
    def to_rust(self) -> Dict[str, Any]:
        """CONVERT to Rust format."""
        return _rust_response.build_response(
            self.status_code,
            self.body,
            self.headers
        )

    def is_json(self) -> bool:
        """Check if response content is JSON."""
        return self.headers.get("Content-Type") == "application/json"

    def is_text(self) -> bool:
        """Check if response content is plain text."""
        return self.headers.get("Content-Type") == "text/plain"

    def body_string(self) -> str:
        """Get body as string."""
        if isinstance(self.body, bytes):
            return self.body.decode('utf-8')
        if isinstance(self.body, str):
            return self.body
        return str(self.body)

__all__ = ['Response']
