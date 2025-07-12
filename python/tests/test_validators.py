import pytest
from forzium.validators import validate_buffer_size, validate_utf8_string, validate_u8_range
from forzium.exceptions import ValidationError

class TestValidateBufferSize:
    def test_success_small_buffer(self):
        validate_buffer_size(b"hello")
    
    def test_success_empty_buffer(self):
        validate_buffer_size(b"")
    
    def test_success_max_allowed(self):
        validate_buffer_size(b"x" * 10_485_760)
    
    def test_failure_too_large(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_buffer_size(b"x" * 10_485_761)
        assert "EXCEEDS LIMIT" in str(exc_info.value)
    
    def test_failure_wrong_type(self):
        with pytest.raises(TypeError):
            validate_buffer_size("not bytes")

class TestValidateUtf8String:
    def test_success_ascii(self):
        result = validate_utf8_string(b"Hello, world!")
        assert result == "Hello, world!"
    
    def test_success_empty(self):
        result = validate_utf8_string(b"")
        assert result == ""
    
    def test_success_unicode(self):
        text = "天城越え 🌍"
        result = validate_utf8_string(text.encode('utf-8'))
        assert result == text
    
    def test_failure_invalid_utf8(self):
        with pytest.raises(ValueError):
            validate_utf8_string(b"\xff\xfe\xfd")
    
    def test_failure_wrong_type(self):
        with pytest.raises(TypeError):
            validate_utf8_string("already string")

class TestValidateU8Range:
    def test_success_min(self):
        result = validate_u8_range(0)
        assert result == 0
    
    def test_success_max(self):
        result = validate_u8_range(255)
        assert result == 255
    
    def test_success_mid(self):
        result = validate_u8_range(128)
        assert result == 128
    
    def test_failure_negative(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_u8_range(-1)
        assert "out of u8 range" in str(exc_info.value)
    
    def test_failure_too_large(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_u8_range(256)
        assert "out of u8 range" in str(exc_info.value)
    
    def test_failure_wrong_type(self):
        with pytest.raises(ValidationError):
            validate_u8_range("not int")
