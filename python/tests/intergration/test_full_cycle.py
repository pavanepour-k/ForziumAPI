import pytest
from forzium.routing import Router
from forzium.request import Request, RequestHandler
from forzium.dependencies import DependencyInjector

class UserService:
    def get_user(self, user_id: str):
        return {"id": user_id, "name": f"User {user_id}"}

@pytest.mark.asyncio
async def test_full_request_cycle():
    handler = RequestHandler()
    handler.injector.register(UserService, UserService, singleton=True)
    
    @handler.route("/users/{user_id}", methods=["GET"])
    async def get_user(request: Request, user_id: str, user_service: UserService):
        user = user_service.get_user(user_id)
        return {"user": user, "method": request.method}
    
    request = Request(
        method="GET",
        path="/users/123",
        headers={"Accept": "application/json"},
        query_params={}
    )
    
    response = await handler.handle_request(request)
    
    assert response["user"]["id"] == "123"
    assert response["method"] == "GET"

@pytest.mark.asyncio
async def test_json_parsing():
    request = Request(
        method="POST",
        path="/api/data",
        headers={"Content-Type": "application/json"},
        query_params={},
        body=b'{"key": "value", "number": 42}'
    )
    
    data = await request.json()
    assert data["key"] == "value"
    assert data["number"] == 42

@pytest.mark.asyncio
async def test_form_parsing():
    request = Request(
        method="POST",
        path="/api/form",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        query_params={},
        body=b'name=John+Doe&email=john%40example.com'
    )
    
    data = await request.form()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"

@pytest.mark.asyncio
async def test_query_parsing():
    request = Request(
        method="GET",
        path="/api/search",
        headers={},
        query_params={"q": "test query", "page": "1"}
    )
    
    params = request.parse_query()
    assert params["q"] == "test query"
    assert params["page"] == "1"

@pytest.mark.asyncio
async def test_middleware_chain():
    handler = RequestHandler()
    
    async def auth_middleware(request: Request):
        request.headers["X-Authenticated"] = "true"
        return request
    
    async def logging_middleware(request: Request):
        request.headers["X-Logged"] = "true"
        return request
    
    handler.add_middleware(auth_middleware)
    handler.add_middleware(logging_middleware)
    
    @handler.route("/test", methods=["GET"])
    async def test_endpoint(request: Request):
        return {
            "authenticated": request.headers.get("X-Authenticated"),
            "logged": request.headers.get("X-Logged")
        }
    
    request = Request(
        method="GET",
        path="/test",
        headers={},
        query_params={}
    )
    
    response = await handler.handle_request(request)
    assert response["authenticated"] == "true"
    assert response["logged"] == "true"

@pytest.mark.asyncio
async def test_dependency_injection():
    class Database:
        def query(self, sql: str):
            return [{"id": 1, "data": "test"}]
    
    class CacheService:
        def __init__(self):
            self.cache = {}
        
        def get(self, key: str):
            return self.cache.get(key)
        
        def set(self, key: str, value: Any):
            self.cache[key] = value
    
    handler = RequestHandler()
    handler.injector.register(Database, Database, singleton=True)
    handler.injector.register(CacheService, CacheService, singleton=True)
    
    @handler.route("/data", methods=["GET"])
    async def get_data(request: Request, db: Database, cache: CacheService):
        cached = cache.get("data")
        if cached:
            return {"source": "cache", "data": cached}
        
        data = db.query("SELECT * FROM table")
        cache.set("data", data)
        return {"source": "database", "data": data}
    
    request = Request(method="GET", path="/data", headers={}, query_params={})
    
    response1 = await handler.handle_request(request)
    assert response1["source"] == "database"
    
    response2 = await handler.handle_request(request)
    assert response2["source"] == "cache"

@pytest.mark.asyncio
async def test_error_handling():
    handler = RequestHandler()
    
    @handler.route("/error", methods=["GET"])
    async def error_endpoint(request: Request):
        raise ValueError("Test error")
    
    request = Request(method="GET", path="/error", headers={}, query_params={})
    
    with pytest.raises(ValueError, match="Test error"):
        await handler.handle_request(request)

@pytest.mark.asyncio
async def test_multiple_methods():
    handler = RequestHandler()
    
    @handler.route("/resource", methods=["GET", "POST", "PUT", "DELETE"])
    async def resource_endpoint(request: Request):
        return {"method": request.method}
    
    for method in ["GET", "POST", "PUT", "DELETE"]:
        request = Request(method=method, path="/resource", headers={}, query_params={})
        response = await handler.handle_request(request)
        assert response["method"] == method