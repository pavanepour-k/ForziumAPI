from typing import Callable, Dict, Any, Optional, List
import asyncio
from functools import wraps
from ..routing import Router
from ..dependencies import DependencyInjector
from . import Request

class RequestHandler:
    """FastAPI-compatible request handler."""
    
    def __init__(self):
        self.router = Router()
        self.injector = DependencyInjector()
        self.middleware: List[Callable] = []
    
    def route(self, path: str, methods: Optional[List[str]] = None):
        """Decorator for route registration."""
        if methods is None:
            methods = ["GET"]
        
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(request: Request, **kwargs):
                # Inject dependencies
                deps = await self.injector.resolve_all(func)
                
                # Apply middleware
                for mw in self.middleware:
                    request = await mw(request)
                
                # Call handler
                if asyncio.iscoroutinefunction(func):
                    return await func(request, **deps, **kwargs)
                else:
                    return func(request, **deps, **kwargs)
            
            # Register route for each method
            for method in methods:
                self.router.add_route(path, method, wrapper)
            
            return wrapper
        return decorator
    
    def add_middleware(self, middleware: Callable):
        """Add middleware to the stack."""
        self.middleware.append(middleware)
    
    async def handle_request(self, request: Request) -> Any:
        """Handle incoming request."""
        handler, params = self.router.match(request.path, request.method)
        return await handler(request, **params)