from typing import Union, Optional, Final
import logging
import functools
import time
from .. import _rust_lib
from ..metrics import ffi_calls_total, ffi_duration_seconds

MINIMUM_RUST_VERSION: Final[str] = "0.1.0"
if hasattr(_rust_lib, "__version__"):
    if _rust_lib.__version__ < MINIMUM_RUST_VERSION:
        raise ImportError(f"RUST LIBRARY VERSION {_rust_lib.__version__} < {MINIMUM_RUST_VERSION}")

logger = logging.getLogger(__name__)

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

__all__ = ['validate_buffer_size', 'validate_utf8_string', 'validate_u8_range']
