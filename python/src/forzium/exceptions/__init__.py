from typing import Dict, Any, Optional

class ProjectError(Exception):
    """BASE ERROR CLASS."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

class ValidationError(ProjectError):
    """VALIDATION ERRORS."""
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        code = "PYTHON_VALIDATION_ERROR"
        if field:
            message = f"{field}: {message}"
        super().__init__(code, message)
        self.field = field
        self.value = value

class ProcessingError(ProjectError):
    """PROCESSING ERRORS."""
    def __init__(self, message: str):
        super().__init__("PYTHON_PROCESSING_ERROR", message)

class TimeoutError(ProjectError):
    """TIMEOUT ERRORS."""
    def __init__(self, timeout: int):
        super().__init__("PYTHON_TIMEOUT_ERROR", f"Operation exceeded {timeout}s timeout")
        self.timeout = timeout

class SystemError(ProjectError):
    """SYSTEM ERRORS."""
    def __init__(self, message: str):
        super().__init__("PYTHON_SYSTEM_ERROR", message)

__all__ = ['ProjectError', 'ValidationError', 'ProcessingError', 'TimeoutError', 'SystemError']
