"""Deployment configuration and scripts."""

from __future__ import annotations

import os
from typing import List

from infrastructure.configuration import load_settings


def build(image: str) -> List[str]:
    """Return the shell command to build the service image."""
    return ["docker", "build", "-t", image, "."]


def run(image: str) -> List[str]:
    """Return the shell command to run the service."""
    return ["docker", "run", "--rm", image]


def deployment_check() -> List[str]:
    """Return configuration issues preventing production deployment."""

    issues: List[str] = []
    try:
        settings = load_settings()
    except ValueError as exc:
        issues.append(str(exc))
        return issues
    if (
        settings.environment == "prod"
        and os.getenv("FORZIUM_SECRET") in {None, "", "secret"}
    ):
        issues.append("FORZIUM_SECRET must be set for production")
    return issues


__all__ = ["build", "run", "deployment_check"]