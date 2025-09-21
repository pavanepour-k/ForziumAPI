"""Environment-specific configuration loader."""

from __future__ import annotations

import os
from dataclasses import dataclass


ALLOWED_ENVS = {"dev", "prod"}



@dataclass
class Settings:
    """Runtime settings populated from the environment."""

    environment: str = "dev"
    debug: bool = False

def validate_settings(settings: Settings) -> None:
    """Validate *settings* for safe operation.

    Raises
    ------
    ValueError
        If the environment is unsupported or if production settings are
        insecure.
    """

    env = settings.environment
    if env not in ALLOWED_ENVS:
        raise ValueError(f"Unsupported environment: {env}")
    if env == "prod" and settings.debug:
        raise ValueError("Debug must be disabled in production")


def load_settings() -> Settings:
    """Return configuration derived from `FORZIUM_*` variables."""

    env = os.getenv("FORZIUM_ENV", "dev").lower()
    debug = os.getenv("FORZIUM_DEBUG", "0").lower() in {"1", "true", "yes"}
    settings = Settings(environment=env, debug=debug)
    validate_settings(settings)
    return settings


__all__ = ["Settings", "load_settings", "validate_settings", "ALLOWED_ENVS"]