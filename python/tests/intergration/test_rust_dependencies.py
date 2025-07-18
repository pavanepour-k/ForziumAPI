# python/tests/integration/test_rust_dependencies.py
import pytest
from forzium.dependencies import DependencyInjector
from forzium._rust.dependencies import PyDependencyResolver

def test_rust_dependency_resolver():
    """VERIFY Rust dependency resolver integration."""
    rust_resolver = PyDependencyResolver()

    # REGISTER dependencies
    rust_resolver.register("database", "singleton")
    rust_resolver.register("cache", "request")
    rust_resolver.register("logger", "transient")

    # VERIFY registration
    keys = rust_resolver.get_registered_keys()
    assert "database" in keys
    assert "cache" in keys
    assert "logger" in keys

    # TEST scope clearing
    rust_resolver.clear_request_scope()
