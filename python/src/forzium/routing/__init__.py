from typing import Dict, Tuple, Callable, Any
from .._rust import PyRouteMatcher
from ..metrics import ffi_calls_total

class Router:
    def __init__(self):
        self._matcher = PyRouteMatcher()
        self._handlers: Dict[str, Callable] = {}
    
    def add_route(self, path: str, method: str, handler: Callable) -> None:
        handler_id = f"{method}:{path}"
        self._matcher.add_route(path, method, handler_id)
        self._handlers[handler_id] = handler
    
    def match(self, path: str, method: str) -> Tuple[Callable, Dict[str, str]]:
        try:
            handler_id, params = self._matcher.match_path(path, method)
            ffi_calls_total.labels(function="match_path", status="success").inc()
            handler = self._handlers.get(handler_id)
            if not handler:
                raise ValueError(f"Handler not found for {handler_id}")
            return handler, params
        except Exception as e:
            ffi_calls_total.labels(function="match_path", status="error").inc()
            raise

__all__ = ['Router']