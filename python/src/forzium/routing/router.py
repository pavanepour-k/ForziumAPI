"""FastAPI-compatible router implementation backed by Rust."""
from typing import Dict, Tuple, Callable, Any, Optional, List
from dataclasses import dataclass, field
import logging

from .._rust import PyRouteMatcher
from ..exceptions import ValidationError
from ..metrics import ffi_calls_total

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteInfo:
    """Route information container."""
    path: str
    method: str
    handler: Callable
    tags: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    description: Optional[str] = None


class Router:
    """HTTP router with Rust-powered path matching."""
    
    def __init__(self, prefix: str = ""):
        self._prefix = prefix
        self._matcher = PyRouteMatcher()
        self._handlers: Dict[str, Callable] = {}
        self._routes: List[RouteInfo] = []
    
    def add_route(
        self, 
        path: str, 
        method: str, 
        handler: Callable,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """Add a route to the router."""
        full_path = self._prefix + path
        handler_id = f"{method}:{full_path}"
        
        try:
            self._matcher.add_route(full_path, method, handler_id)
            self._handlers[handler_id] = handler
            self._routes.append(RouteInfo(
                path=full_path,
                method=method,
                handler=handler,
                tags=tags or [],
                summary=summary,
                description=description
            ))
            logger.info(f"Route registered: {method} {full_path}")
        except Exception as e:
            logger.error(f"Failed to register route: {method} {full_path}", exc_info=e)
            raise ValidationError(
                message=f"Invalid route pattern: {path}",
                field="path",
                value=path
            )
    
    def match(self, path: str, method: str) -> Tuple[Callable, Dict[str, str]]:
        """Match a request path and method to a handler."""
        try:
            handler_id, params = self._matcher.match_path(path, method)
            ffi_calls_total.labels(function="match_path", status="success").inc()
            
            handler = self._handlers.get(handler_id)
            if not handler:
                raise ValueError(f"Handler not found for {handler_id}")
            
            logger.debug(f"Route matched: {method} {path} -> {handler_id}")
            return handler, params
        except Exception as e:
            ffi_calls_total.labels(function="match_path", status="error").inc()
            logger.warning(f"Route not found: {method} {path}")
            raise
    
    def get_routes(self) -> List[RouteInfo]:
        """Get all registered routes."""
        return list(self._routes)
    
    def include_router(self, router: "Router", prefix: str = "") -> None:
        """Include routes from another router."""
        for route in router.get_routes():
            self.add_route(
                path=prefix + route.path,
                method=route.method,
                handler=route.handler,
                tags=route.tags,
                summary=route.summary,
                description=route.description
            )