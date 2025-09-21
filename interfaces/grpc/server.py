"""Start a simple gRPC server for Forzium computations."""

import json
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from core.service.orchestration_service import run_computation, stream_computation

from . import forzium_pb2, forzium_pb2_grpc


class ForziumServicer(forzium_pb2_grpc.ForziumServicer):
    """Dispatch Compute RPCs to the core service."""

    def Compute(self, request, context):  # noqa: N802 - gRPC method
        payload = json.loads(request.payload or "{}")
        result = run_computation(
            payload.get("data", []),
            payload.get("operation", ""),
            payload.get("parameters", {}),
        )
        data = json.dumps(result).encode()
        return forzium_pb2.JsonPayload(payload=data)

    def StreamCompute(self, request, context):  # noqa: N802 - gRPC method
        payload = json.loads(request.payload or "{}")
        rows = stream_computation(
            payload.get("data", []),
            payload.get("operation", ""),
            payload.get("parameters", {}),
        )
        for row in rows:
            data = json.dumps(row).encode()
            yield forzium_pb2.JsonPayload(payload=data)


def start_grpc_server(port: int = 50051) -> grpc.Server:
    """Start the gRPC server on *port* and return it."""

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    forzium_pb2_grpc.add_ForziumServicer_to_server(ForziumServicer(), server)
    health_serv = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_serv, server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    health_serv.set("", health_pb2.HealthCheckResponse.SERVING)
    health_serv.set("forzium.Forzium", health_pb2.HealthCheckResponse.SERVING)
    return server
