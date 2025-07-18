import pytest
from forzium.routing import Router
from forzium.request import Request, RequestHandler
import time

@pytest.mark.benchmark
def test_routing_performance(benchmark):
    handler = RequestHandler()
    
    for i in range(10000):
        @handler.route(f"/api/v1/resource{i}/{{id}}", methods=["GET"])
        async def handle(request, id):
            return {"id": id}
    
    request = Request(
        method="GET",
        path="/api/v1/resource5000/test123",
        headers={},
        query_params={}
    )
    
    result = benchmark(handler.router.match, request.path, request.method)
    assert result[1]["id"] == "test123"

def test_json_parsing_performance(benchmark):
    from forzium._rust import parse_json
    
    data = b'{"users": [' + b','.join(
        f'{{"id": {i}, "name": "User{i}"}}'.encode() 
        for i in range(10000)
    ) + b']}'
    
    result = benchmark(parse_json, data)
    assert len(result["users"]) == 10000

def test_form_parsing_performance(benchmark):
    from forzium._rust import parse_form
    
    data = b'&'.join(
        f'field{i}=value{i}'.encode() for i in range(1000)
    )
    
    result = benchmark(parse_form, data)
    assert len(result) == 1000
    assert result["field500"] == "value500"

def test_query_parsing_performance(benchmark):
    from forzium._rust import parse_query_params
    
    query = '&'.join(f'param{i}=value{i}' for i in range(1000))
    
    result = benchmark(parse_query_params, query)
    assert len(result) == 1000
    assert result["param500"] == "value500"

@pytest.mark.asyncio
async def test_request_handler_throughput(benchmark):
    handler = RequestHandler()
    
    @handler.route("/test/{id}", methods=["GET"])
    async def test_endpoint(request: Request, id: str):
        return {"id": id, "timestamp": time.time()}
    
    async def handle_request():
        request = Request(
            method="GET",
            path="/test/123",
            headers={},
            query_params={}
        )
        return await handler.handle_request(request)
    
    result = await benchmark(handle_request)
    assert result["id"] == "123"

def test_dependency_injection_performance(benchmark):
    from forzium.dependencies import DependencyInjector
    
    class Service1: pass
    class Service2: pass
    class Service3: pass
    class Service4: pass
    class Service5: pass
    
    injector = DependencyInjector()
    injector.register(Service1, Service1)
    injector.register(Service2, Service2)
    injector.register(Service3, Service3)
    injector.register(Service4, Service4)
    injector.register(Service5, Service5)
    
    def resolve_all():
        return [
            injector.get(Service1),
            injector.get(Service2),
            injector.get(Service3),
            injector.get(Service4),
            injector.get(Service5)
        ]
    
    result = benchmark(resolve_all)
    assert len(result) == 5
    assert isinstance(result[0], Service1)

@pytest.mark.asyncio
async def test_middleware_overhead(benchmark):
    handler = RequestHandler()
    
    async def middleware1(request): return request
    async def middleware2(request): return request
    async def middleware3(request): return request
    async def middleware4(request): return request
    async def middleware5(request): return request
    
    handler.add_middleware(middleware1)
    handler.add_middleware(middleware2)
    handler.add_middleware(middleware3)
    handler.add_middleware(middleware4)
    handler.add_middleware(middleware5)
    
    @handler.route("/test", methods=["GET"])
    async def endpoint(request: Request):
        return {"status": "ok"}
    
    async def handle():
        request = Request(method="GET", path="/test", headers={}, query_params={})
        return await handler.handle_request(request)
    
    result = await benchmark(handle)
    assert result["status"] == "ok"