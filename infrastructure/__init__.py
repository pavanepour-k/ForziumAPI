"""Environment-specific configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass
class Settings:
    """Configuration derived from environment variables."""

    environment: str = "development"
    debug: bool = False


def load_settings() -> Settings:
    """Load settings from the current environment."""
    return Settings(
        environment=os.getenv("FORZIUM_ENV", "development"),
        debug=os.getenv("FORZIUM_DEBUG", "0") == "1",
    )
