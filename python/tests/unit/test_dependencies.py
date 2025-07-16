import pytest
from forzium.dependencies import DependencyInjector
import asyncio

class TestService:
    def __init__(self):
        self.value = "test"

class Database:
    def __init__(self):
        self.connected = True

def test_basic_registration_and_resolution():
    injector = DependencyInjector()
    injector.register(TestService, TestService)
    
    instance = injector.get(TestService)
    assert isinstance(instance, TestService)
    assert instance.value == "test"

def test_singleton_behavior():
    injector = DependencyInjector()
    injector.register(TestService, TestService, singleton=True)
    
    instance1 = injector.get(TestService)
    instance2 = injector.get(TestService)
    
    assert instance1 is instance2

def test_non_singleton_behavior():
    injector = DependencyInjector()
    injector.register(TestService, TestService, singleton=False)
    
    instance1 = injector.get(TestService)
    instance2 = injector.get(TestService)
    
    assert instance1 is not instance2

def test_unregistered_dependency():
    injector = DependencyInjector()
    
    with pytest.raises(ValueError, match="Dependency .* not registered"):
        injector.get(TestService)

def test_factory_function():
    injector = DependencyInjector()
    
    def create_service():
        return TestService()
    
    injector.register(TestService, create_service)
    instance = injector.get(TestService)
    
    assert isinstance(instance, TestService)

# TODO: def test_get_dependencies