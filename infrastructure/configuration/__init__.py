"""Environment-specific configuration loader."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Runtime settings populated from the environment."""

    environment: str = "dev"
    debug: bool = False


def load_settings() -> Settings:
    """Return configuration derived from `FORZIUM_*` variables."""
    env = os.getenv("FORZIUM_ENV", "dev")
    debug = os.getenv("FORZIUM_DEBUG", "0").lower() in {"1", "true", "yes"}
    return Settings(environment=env, debug=debug)
