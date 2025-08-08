"""Test gRPC health check service."""

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from interfaces.grpc.server import start_grpc_server


def test_grpc_health() -> None:
    port = 50052
    server = start_grpc_server(port)
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = health_pb2_grpc.HealthStub(channel)
    resp = stub.Check(health_pb2.HealthCheckRequest(service=""))
    assert resp.status == health_pb2.HealthCheckResponse.SERVING
    server.stop(0)
