from pathlib import Path
from typing import Optional

class Settings:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
    RUST_LIB_DIR = PROJECT_ROOT / "rust" / "target" / "release"
    
    MAX_BUFFER_SIZE: int = 10_485_760
    DEFAULT_TIMEOUT: float = 30.0
    
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    VERSION: str = "0.1.0"

settings = Settings()
