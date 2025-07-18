import re
from typing import Dict, Any

class Router:
    """Router for handling route registration and matching."""
    def __init__(self):
        self._routes = []

    def add_route(self, path: str, method: str, handler):
        # Convert path pattern to regex
        pattern = '^' + re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', path) + '$'
        regex = re.compile(pattern)
        self._routes.append((regex, method.upper(), handler))

    def route(self, path: str, methods=None):
        if methods is None:
            methods = ['GET']
        def decorator(func):
            for m in methods:
                self.add_route(path, m, func)
            return func
        return decorator

    def match(self, path: str, method: str):
        method = method.upper()
        for regex, m, handler in self._routes:
            if m != method:
                continue
            match = regex.match(path)
            if match:
                return handler, match.groupdict()
        raise ValueError(f"No matching route for {method} {path}")
