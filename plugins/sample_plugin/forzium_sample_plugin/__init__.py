"""Sample plugin package used solely for integration testing."""

from __future__ import annotations

__all__ = ("PLUGIN_IDENTIFIER",)

# Exposed constant to prove module import works during tests
PLUGIN_IDENTIFIER = "forzium.sample-plugin"