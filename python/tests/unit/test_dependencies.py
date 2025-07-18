import pytest
from typing import Optional, Dict, Any
from forzium.dependencies import DependencyInjector
from forzium.request import Request

# Dummy classes to use as dependency types
class UserService:
    pass

class Database:
    pass

class CacheService:
    pass

def test_get_dependencies():
    """TEST dependency extraction from function signature."""
    injector = DependencyInjector()

    # SAMPLE function with dependencies
    def sample_handler(
        request: Request,
        user_service: UserService,
        db: Database,
        cache: Optional[CacheService] = None
    ) -> Dict[str, Any]:
        return {"status": "ok"}

    # EXTRACT dependencies
    deps = injector.get_dependencies(sample_handler)

    # VERIFY
    assert 'user_service' in deps
    assert deps['user_service'] == UserService
    assert 'db' in deps
    assert deps['db'] == Database
    assert 'cache' in deps
    assert deps['cache'] == Optional[CacheService]

    # REQUEST should be excluded
    assert 'request' not in deps

def test_circular_dependency_detection():
    """TEST circular dependency detection."""
    injector = DependencyInjector()

    class ServiceA:
        def __init__(self, service_b: 'ServiceB'):
            self.service_b = service_b

    class ServiceB:
        def __init__(self, service_a: ServiceA):
            self.service_a = service_a

    injector.register(ServiceA, lambda: ServiceA(injector.get(ServiceB)))
    injector.register(ServiceB, lambda: ServiceB(injector.get(ServiceA)))

    with pytest.raises(ValueError, match="Circular dependency detected"):
        injector.get(ServiceA)
