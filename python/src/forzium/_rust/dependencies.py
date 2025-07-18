class PyDependencyResolver:
    """Stub for Rust PyDependencyResolver."""
    def __init__(self):
        self._registry = {}

    def register(self, key, scope):
        self._registry[key] = scope

    def get_registered_keys(self):
        return list(self._registry.keys())

    def clear_request_scope(self):
        keys_to_remove = [k for k, v in self._registry.items() if v == "request"]
        for k in keys_to_remove:
            del self._registry[k]
