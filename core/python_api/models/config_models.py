"""Application configuration model without Pydantic."""

from dataclasses import dataclass


@dataclass
class Settings:
    """Simple settings dataclass used by the FastAPI app."""

    app_name: str = "Forzium API"
    version: str = "1.0.0"