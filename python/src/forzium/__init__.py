import logging
from pathlib import Path

# STEP 1: LOGGING FIRST
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# STEP 2: VERSION CHECK
__version__ = "0.1.0"
logger.info(f"INITIALIZING {__name__} v{__version__}")

# STEP 3: VALIDATE RUST LIBRARY PRESENCE
_RUST_LIB_PATH = Path(__file__).parent / "_rust_lib.so"  # Linux/Mac
if not _RUST_LIB_PATH.exists():
    _RUST_LIB_PATH = Path(__file__).parent / "_rust_lib.pyd"  # Windows
    
if not _RUST_LIB_PATH.exists():
    raise ImportError(f"RUST LIBRARY NOT FOUND AT {_RUST_LIB_PATH}")

# STEP 4: RUST MODULE IMPORT
try:
    from ._rust import *
    logger.info("RUST MODULE LOADED")
except ImportError as e:
    logger.error(f"RUST MODULE FAILED: {e}")
    raise

# STEP 5: PYTHON MODULES
from .api import *
from .core import *
from .validators import *
from .exceptions import *
from .routing import Router

# STEP 6: VALIDATION
def _validate_installation():
    """VALIDATE COMPLETE INSTALLATION."""
    required_functions = ['validate_buffer_size', 'validate_utf8_string', 'validate_u8_range']
    for func in required_functions:
        if func not in globals():
            logger.warning(f"MISSING FUNCTION: {func} - May not be exported from _rust")

_validate_installation()
