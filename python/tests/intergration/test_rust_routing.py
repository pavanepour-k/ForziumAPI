# python/tests/integration/test_rust_routing.py
import pytest
from forzium.routing import Router
from forzium._rust import PyRouteMatcher

def test_rust_route_matcher():
    """VERIFY Rust route matching works correctly."""
    router = Router()

    # ADD routes
    router.add_route("/users/{id}", "GET", lambda: "user_handler")
    router.add_route("/posts/{post_id}/comments/{comment_id}", "GET", lambda: "comment_handler")

    # TEST matching
    handler, params = router.match("/users/123", "GET")
    assert params == {"id": "123"}

    handler, params = router.match("/posts/456/comments/789", "GET")
    assert params == {"post_id": "456", "comment_id": "789"}

    # TEST non-existent route
    with pytest.raises(ValueError):
        router.match("/nonexistent", "GET")
