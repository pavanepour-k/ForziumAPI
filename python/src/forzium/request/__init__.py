from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass
import json
from .._rust import parse_query_params, parse_json, parse_form
from ..exceptions import ValidationError

@dataclass
class Request:
    """HTTP request representation."""
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[Union[bytes, Dict[str, Any]]] = None
    
    @classmethod
    def from_fastapi(cls, request):
        """Create from FastAPI request object."""
        return cls(
            method=request.method,
            path=request.url.path,
            headers=dict(request.headers),
            query_params=dict(request.query_params),
            body=None
        )
    
    def parse_query(self) -> Dict[str, str]:
        """Parse query string using Rust."""
        if hasattr(self, '_parsed_query'):
            return self._parsed_query
        
        query_string = "&".join(f"{k}={v}" for k, v in self.query_params.items())
        self._parsed_query = parse_query_params(query_string)
        return self._parsed_query
    
    async def json(self) -> Dict[str, Any]:
        """Parse JSON body using Rust."""
        if isinstance(self.body, dict):
            return self.body
        
        if isinstance(self.body, bytes):
            try:
                return parse_json(self.body)
            except Exception as e:
                raise ValidationError(f"Invalid JSON: {e}", field="body", value=None)
        
        raise ValidationError("No body to parse", field="body", value=None)
    
    async def form(self) -> Dict[str, str]:
        """Parse form body using Rust."""
        if isinstance(self.body, bytes):
            try:
                return parse_form(self.body)
            except Exception as e:
                raise ValidationError(f"Invalid form data: {e}", field="body", value=None)
        
        raise ValidationError("No form data to parse", field="body", value=None)

__all__ = ['Request']