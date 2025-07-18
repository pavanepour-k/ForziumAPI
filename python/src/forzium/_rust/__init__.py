from .dependencies import PyDependencyResolver
from .response import PyResponseBuilder

class PyRouteMatcher:
    """Stub for Rust route matcher."""
    pass

def validate_buffer_size(data: bytes):
    """Validate buffer size (stub)."""
    # Example stub: do nothing or minimal check
    return None

def validate_utf8_string(data: bytes):
    """Validate that data is valid UTF-8 (stub)."""
    data.decode('utf-8')  # Will raise if not valid
    return None

# alias
validate_u8_range = validate_buffer_size
