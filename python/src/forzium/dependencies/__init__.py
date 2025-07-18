from typing import Dict, Any, Callable, Optional
import inspect
from functools import lru_cache

class DependencyInjector:
    """Dependency injection system."""
    
    def __init__(self):
        self._factories: Dict[type, tuple[Callable, bool]] = {}
        self._singletons: Dict[type, Any] = {}
    
    def register(self, dep_type: type, factory: Callable, singleton: bool = False):
        """Register a dependency factory."""
        self._factories[dep_type] = (factory, singleton)
    
    def get(self, dep_type: type) -> Any:
        """Resolve a dependency."""
        if dep_type in self._singletons:
            return self._singletons[dep_type]
        
        if dep_type not in self._factories:
            raise ValueError(f"Dependency {dep_type} not registered")
        
        factory, is_singleton = self._factories[dep_type]
        instance = factory()
        
        if is_singleton:
            self._singletons[dep_type] = instance
        
        return instance
    
    @lru_cache(maxsize=128)
    def get_dependencies(self, func: Callable) -> Dict[str, type]:
        """Extract dependencies from function signature."""
        sig = inspect.signature(func)
        deps = {}
        
        for name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                if name not in ['self', 'request', 'response']:
                    deps[name] = param.annotation
        
        return deps
    
    async def resolve_all(self, func: Callable) -> Dict[str, Any]:
        """Resolve all dependencies for a function."""
        deps = self.get_dependencies(func)
        resolved = {}
        
        for name, dep_type in deps.items():
            resolved[name] = self.get(dep_type)
        
        return resolved

__all__ = ['DependencyInjector']