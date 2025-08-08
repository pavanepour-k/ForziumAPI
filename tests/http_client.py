"""Expose stdlib HTTP helpers for tests."""

from .test_http_client import Response, get, post

__all__ = ["Response", "get", "post"]
