"""Forzium Python helpers."""

__version__ = "0.1.0"  # Reason: freeze public API with version constant

from ._ffi.validation import ComputeRequest
from .app import ForziumApp
from .dependency import Depends
from .http import BackgroundTask, BackgroundTasks, Request, Response
from .middleware import (
    BaseHTTPMiddleware,
    CORSMiddleware,
    GZipMiddleware,
    HTTPSRedirectMiddleware,
    TrustedHostMiddleware,
    SessionMiddleware,
    FileSessionMiddleware,
    JWTMiddleware,
)
from .templates import TemplateRenderer
from .testclient import Response as TestResponse, TestClient
from .websockets import WebSocket, WebSocketRoute
from interfaces.shared_types.compute_request import ComputeRequestModel
from .http2 import push

__all__ = [
    "__version__",
    "ComputeRequest",
    "ComputeRequestModel",
    "ForziumApp",
    "Depends",
    "BaseHTTPMiddleware",
    "CORSMiddleware",
    "GZipMiddleware",
    "HTTPSRedirectMiddleware",
    "TrustedHostMiddleware",
    "SessionMiddleware",
    "FileSessionMiddleware",
    "JWTMiddleware",
    "BackgroundTask",
    "BackgroundTasks",
    "Request",
    "Response",
    "TemplateRenderer",
    "WebSocket",
    "WebSocketRoute",
    "TestClient",
    "TestResponse",
    "push",
]