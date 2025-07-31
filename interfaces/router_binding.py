import json
from fastapi.routing import APIRoute
from fastapi import FastAPI
from core.python_api.services.orchestration_service import run_computation, stream_computation


def register_routes(server, app: FastAPI) -> None:
    """Register FastAPI routes with the Rust server."""
    for route in app.router.routes:
        if isinstance(route, APIRoute):
              if route.path == "/health" and "GET" in route.methods:
                  def health_handler(_body: bytes) -> tuple[int, str]:
                      return 200, json.dumps({"status": "ok"})
                  server.add_route("GET", "/health", health_handler)
              elif route.path == "/compute" and "POST" in route.methods:
                  def compute_handler(body: bytes) -> tuple[int, str]:
                      payload = json.loads(body.decode())
                      try:
                          result = run_computation(
                              payload.get("data"),
                              payload.get("operation"),
                              payload.get("parameters", {}),
                          )
                          return 200, json.dumps(result)
                      except ValueError as exc:
                          return 400, json.dumps({"detail": str(exc)})
                  server.add_route("POST", "/compute", compute_handler)
              elif route.path == "/stream" and "POST" in route.methods:
                  def stream_handler(body: bytes) -> tuple[int, str]:
                      payload = json.loads(body.decode())
                      try:
                          rows = list(
                              stream_computation(
                                  payload.get("data"),
                                  payload.get("operation"),
                                  payload.get("parameters", {}),
                              )
                          )
                          text = "\n".join(json.dumps(r) for r in rows)
                          return 200, text
                      except ValueError as exc:
                          return 400, json.dumps({"detail": str(exc)})
                  server.add_route("POST", "/stream", stream_handler)
