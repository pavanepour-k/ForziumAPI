import pytest
from forzium.routing import Router

@pytest.fixture
def large_router():
    router = Router()
    for i in range(10000):
        router.add_route(f"/api/v1/resource{i}/{{id}}", "GET", lambda: None)
    return router

def test_route_matching_performance(benchmark, large_router):
    result = benchmark(large_router.match, "/api/v1/resource5000/123", "GET")
    assert result[1] == {"id": "123"}

def test_route_registration_performance(benchmark):
    router = Router()
    benchmark(router.add_route, "/test/{id}", "GET", lambda: None)