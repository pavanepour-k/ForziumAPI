import logging

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Version
__version__ = "0.1.0"
logger.info(f"INITIALIZING {__name__} v{__version__}")

# Import Python modules
from .routing import Router
from .dependencies import DependencyInjector
from .request import Request, RequestHandler
from .response import Response

# Import validation functions from Rust stubs
from ._rust import validate_buffer_size, validate_utf8_string, validate_u8_range

__all__ = [
    'Router', 'DependencyInjector', 'Request', 'RequestHandler',
    'Response', 'validate_buffer_size', 'validate_utf8_string',
    'validate_u8_range', '__version__'
]
