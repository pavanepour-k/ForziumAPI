import inspect
from typing import Dict

class DependencyInjector:
    """Simple dependency injection system."""
    def __init__(self):
        self._registry = {}
        self._resolving = set()
        self._singletons = {}

    def register(self, cls, factory, singleton=False):
        """Register a dependency. Factory can be a callable or a class."""
        self._registry[cls] = {'factory': factory, 'singleton': singleton}

    def get(self, cls):
        """Get an instance of the registered dependency, handling singleton scope."""
        if cls in self._resolving:
            raise ValueError("Circular dependency detected")
        self._resolving.add(cls)

        if cls not in self._registry:
            self._resolving.remove(cls)
            raise ValueError(f"Dependency {cls} not registered")
        entry = self._registry[cls]
        if entry['singleton']:
            if cls not in self._singletons:
                entry_factory = entry['factory']
                instance = entry_factory() if callable(entry_factory) else entry_factory
                self._singletons[cls] = instance
            result = self._singletons[cls]
        else:
            entry_factory = entry['factory']
            result = entry_factory() if callable(entry_factory) else entry_factory

        self._resolving.remove(cls)
        return result

    def get_dependencies(self, func):
        """Extract dependencies from function signature, excluding Request."""
        deps = {}
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            if name == 'request':
                continue
            annotation = param.annotation
            if annotation is inspect._empty:
                continue
            if annotation is None:
                continue
            deps[name] = annotation
        return deps

    async def resolve_all(self, func):
        """Resolve all dependencies for a handler function asynchronously."""
        sig = inspect.signature(func)
        resolved = {}
        for name, param in sig.parameters.items():
            if name == 'request':
                continue
            annotation = param.annotation
            if annotation in self._registry:
                instance = self.get(annotation)
                resolved[name] = instance
        return resolved
