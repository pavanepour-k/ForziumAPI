# python/tests/integration/test_full_request_cycle.py
import pytest
import asyncio
import json
from forzium import Router, Request, Response, DependencyInjector

@pytest.mark.asyncio
async def test_complete_request_processing():
    """TEST complete request processing pipeline."""
    # SETUP
    router = Router()
    injector = DependencyInjector()

    # REGISTER service
    class UserService:
        def get_user(self, user_id: str):
            return {"id": user_id, "name": f"User {user_id}"}

    injector.register(UserService, UserService, singleton=True)

    # DEFINE handler
    @router.route("/users/{user_id}", methods=["GET"])
    async def get_user(request: Request, user_id: str, service: UserService):
        user = service.get_user(user_id)
        return Response.json({"user": user})

    # SIMULATE request
    request = Request(
        method="GET",
        path="/users/123",
        headers={"Accept": "application/json"},
        query_params={}
    )

    # PROCESS request
    handler, params = router.match(request.path, request.method)
    deps = await injector.resolve_all(handler)
    response = await handler(request, **params, **deps)

    # VERIFY response
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert "user" in json.loads(response.body)
