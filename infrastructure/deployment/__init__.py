"""Deployment configuration and scripts."""

from __future__ import annotations

from typing import List


def build(image: str) -> List[str]:
    """Return the shell command to build the service image."""
    return ["docker", "build", "-t", image, "."]


def run(image: str) -> List[str]:
    """Return the shell command to run the service."""
    return ["docker", "run", "--rm", image]
