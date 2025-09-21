"""Forzium Python helpers."""

__version__ = "0.1.4"  # Reason: freeze public API with version constant

from interfaces.shared_types.compute_request import ComputeRequestModel

from ._ffi.validation import ComputeRequest
from .app import ForziumApp
from .dependency import Depends
from .http import BackgroundTask, BackgroundTasks, Request, Response
from .http2 import push
from .middleware import (
    BaseHTTPMiddleware,
    CORSMiddleware,
    FileSessionMiddleware,
    GZipMiddleware,
    HTTPSRedirectMiddleware,
    JWTMiddleware,
    RateLimitMiddleware,
    RequestLoggerMiddleware,
    SessionMiddleware,
    SecurityHeadersMiddleware,
    StaticFilesMiddleware,
    TrustedHostMiddleware,
)
from .templates import TemplateRenderer
from .task_queue import CeleryTaskQueue, RedisTaskQueue
from .testclient import Response as TestResponse
from .testclient import TestClient
from .websockets import WebSocket, WebSocketRoute

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
    "RateLimitMiddleware",
    "RequestLoggerMiddleware",
    "SecurityHeadersMiddleware",
    "StaticFilesMiddleware",
    "BackgroundTask",
    "BackgroundTasks",
    "RedisTaskQueue",
    "CeleryTaskQueue",
    "Request",
    "Response",
    "TemplateRenderer",
    "WebSocket",
    "WebSocketRoute",
    "TestClient",
    "TestResponse",
    "push",
]