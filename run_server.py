"""Run the Forzium application using the Rust HTTP server."""

import time
from core import app
from forzium_engine import ForziumHttpServer
from interfaces import register_routes


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ForziumHttpServer()
    register_routes(server, app)
    server.serve(f"{host}:{port}")
    print(f"Forzium server running on {host}:{port}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()