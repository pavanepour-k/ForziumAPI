import pytest
from forzium.routing import Router

def test_basic_routing():
    router = Router()
    
    def user_handler(user_id: str):
        return f"User {user_id}"
    
    router.add_route("/users/{user_id}", "GET", user_handler)
    
    handler, params = router.match("/users/123", "GET")
    assert handler == user_handler
    assert params == {"user_id": "123"}

def test_multiple_params():
    router = Router()
    
    def item_handler(category: str, item_id: str):
        return f"{category}/{item_id}"
    
    router.add_route("/shop/{category}/items/{item_id}", "GET", item_handler)
    
    handler, params = router.match("/shop/electronics/items/456", "GET")
    assert params == {"category": "electronics", "item_id": "456"}

def test_route_not_found():
    router = Router()
    
    with pytest.raises(ValueError, match="No route found"):
        router.match("/nonexistent", "GET")

def test_method_mismatch():
    router = Router()
    
    def handler():
        return "OK"
    
    router.add_route("/test", "GET", handler)
    
    with pytest.raises(ValueError, match="No route found"):
        router.match("/test", "POST")