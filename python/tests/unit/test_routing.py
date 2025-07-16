import pytest
from forzium.routing import Router

def test_basic_route():
    router = Router()
    handler = lambda req: {"response": "ok"}
    
    router.add_route("/test", "GET", handler)
    matched_handler, params = router.match("/test", "GET")
    
    assert matched_handler == handler
    assert params == {}

def test_parametric_route():
    router = Router()
    handler = lambda req, id: {"id": id}
    
    router.add_route("/users/{id}", "GET", handler)
    matched_handler, params = router.match("/users/123", "GET")
    
    assert matched_handler == handler
    assert params == {"id": "123"}

def test_multiple_parameters():
    router = Router()
    handler = lambda req, category, id: {"category": category, "id": id}
    
    router.add_route("/products/{category}/{id}", "GET", handler)
    matched_handler, params = router.match("/products/electronics/456", "GET")
    
    assert matched_handler == handler
    assert params == {"category": "electronics", "id": "456"}

def test_multiple_methods():
    router = Router()
    get_handler = lambda req: {"method": "GET"}
    post_handler = lambda req: {"method": "POST"}
    
    router.add_route("/resource", "GET", get_handler)
    router.add_route("/resource", "POST", post_handler)
    
    get_matched, _ = router.match("/resource", "GET")
    post_matched, _ = router.match("/resource", "POST")
    
    assert get_matched == get_handler
    assert post_matched == post_handler

def test_route_not_found():
    router = Router()
    
    with pytest.raises(Exception):
        router.match("/nonexistent", "GET")

def test_method_not_allowed():
    router = Router()
    handler = lambda req: {"response": "ok"}
    
    router.add_route("/test", "GET", handler)
    
    with pytest.raises(Exception):
        router.match("/test", "POST")

def test_special_characters_in_route():
    router = Router()
    handler = lambda req: {"response": "ok"}
    
    router.add_route("/api/v1/test-endpoint", "GET", handler)
    matched_handler, _ = router.match("/api/v1/test-endpoint", "GET")
    
    assert matched_handler == handler

def test_trailing_slash_handling():
    router = Router()
    handler = lambda req: {"response": "ok"}
    
    router.add_route("/test/", "GET", handler)
    matched_handler, _ = router.match("/test/", "GET")
    
    assert matched_handler == handler

def test_router_include():
    main_router = Router()
    sub_router = Router()
    
    sub_handler = lambda req: {"source": "sub"}
    sub_router.add_route("/sub", "GET", sub_handler)
    
    main_router.include_router(sub_router, prefix="/api")
    
    matched_handler, _ = main_router.match("/api/sub", "GET")
    assert matched_handler == sub_handler

def test_get_routes():
    router = Router()
    
    router.add_route(
        "/test",
        "GET",
        lambda: None,
        tags=["test"],
        summary="Test endpoint",
        description="Test description"
    )
    
    routes = router.get_routes()
    assert len(routes) == 1
    assert routes[0].path == "/test"
    assert routes[0].method == "GET"
    assert routes[0].tags == ["test"]
    assert routes[0].summary == "Test endpoint"