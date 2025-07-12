from typing import Union, Any
from .exceptions import ValidationError
from ._rust import validate_buffer_size as _rust_validate_buffer_size
from ._rust import validate_utf8_string as _rust_validate_utf8_string
from ._rust import validate_u8_range as _rust_validate_u8_range

MAX_BUFFER_SIZE = 10_485_760  # 10MB

def validate_buffer_size(data: bytes) -> None:
    if len(data) > MAX_BUFFER_SIZE:
        raise ValidationError(f"BUFFER SIZE {len(data)} EXCEEDS LIMIT {MAX_BUFFER_SIZE}")
    _rust_validate_buffer_size(data)

def validate_utf8_string(data: bytes) -> str:
    try:
        return _rust_validate_utf8_string(data)
    except UnicodeDecodeError as e:
        raise ValidationError(f"INVALID UTF-8: {e}")

def validate_u8_range(value: int) -> int:
    if not isinstance(value, int):
        raise ValidationError(f"Expected int, got {type(value).__name__}", "value", value)
    if value < 0 or value > 255:
        raise ValidationError(f"Value {value} out of u8 range (0-255)", "value", value)
    return _rust_validate_u8_range(value)

__all__ = ['validate_buffer_size', 'validate_utf8_string', 'validate_u8_range']
