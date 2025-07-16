from typing import Union, Optional, Final, Dict, Any
import logging
import functools
import time
import _rust_lib
from ..metrics import ffi_calls_total, ffi_duration_seconds

MINIMUM_RUST_VERSION: Final[str] = "0.1.0"
if hasattr(_rust_lib, "__version__"):
    if _rust_lib.__version__ < MINIMUM_RUST_VERSION:
        raise ImportError(f"RUST LIBRARY VERSION {_rust_lib.__version__} < {MINIMUM_RUST_VERSION}")

logger = logging.getLogger(__name__)

PyRouteMatcher = _rust_lib.PyRouteMatcher

def with_timeout(seconds: float = 30.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                if duration > seconds:
                    raise TimeoutError(f"OPERATION EXCEEDED {seconds}s")
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                ffi_calls_total.labels(function=func.__name__, status=status).inc()
                ffi_duration_seconds.labels(function=func.__name__).observe(duration)
        return wrapper
    return decorator

@with_timeout(30.0)
def validate_buffer_size(data: bytes) -> None:
    if not isinstance(data, bytes):
        raise TypeError(f"EXPECTED bytes, GOT {type(data).__name__}")
    
    try:
        _rust_lib.validate_buffer_size(data)
    except Exception as e:
        logger.error(f"RUST VALIDATION FAILED: {e}")
        raise

@with_timeout(30.0)
def validate_utf8_string(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError(f"EXPECTED bytes, GOT {type(data).__name__}")
    
    try:
        result = _rust_lib.validate_utf8_string(data)
        return result
    except Exception as e:
        logger.error(f"RUST UTF8 VALIDATION FAILED: {e}")
        raise

@with_timeout(30.0)
def validate_u8_range(value: int) -> int:
    if not isinstance(value, int):
        raise TypeError(f"EXPECTED int, GOT {type(value).__name__}")
    
    try:
        result = _rust_lib.validate_u8_range(value)
        return result
    except Exception as e:
        logger.error(f"RUST U8 VALIDATION FAILED: {e}")
        raise

@with_timeout(30.0)
def parse_query_params(query: str) -> Dict[str, str]:
    if not isinstance(query, str):
        raise TypeError(f"EXPECTED str, GOT {type(query).__name__}")
    
    try:
        result = _rust_lib.request.parse_query_params(query)
        return result
    except Exception as e:
        logger.error(f"RUST QUERY PARSING FAILED: {e}")
        raise

@with_timeout(30.0)
def parse_json(data: bytes) -> Any:
    if not isinstance(data, bytes):
        raise TypeError(f"EXPECTED bytes, GOT {type(data).__name__}")
    
    try:
        result = _rust_lib.request.parse_json(data)
        return result
    except Exception as e:
        logger.error(f"RUST JSON PARSING FAILED: {e}")
        raise

@with_timeout(30.0)
def parse_form(data: bytes) -> Dict[str, str]:
    if not isinstance(data, bytes):
        raise TypeError(f"EXPECTED bytes, GOT {type(data).__name__}")
    
    try:
        result = _rust_lib.request.parse_form(data)
        return result
    except Exception as e:
        logger.error(f"RUST FORM PARSING FAILED: {e}")
        raise

__all__ = [
    'validate_buffer_size', 
    'validate_utf8_string', 
    'validate_u8_range',
    'parse_query_params',
    'parse_json',
    'parse_form',
    'PyRouteMatcher'
]