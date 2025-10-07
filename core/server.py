"""Server module for Forzium."""
import logging
from typing import Any
from forzium_engine import ForziumHttpServer

LOGGER = logging.getLogger("forzium.server")

# Global server instance
_server: ForziumHttpServer | None = None


def get_server() -> ForziumHttpServer:
    """Get the global server instance."""
    global _server
    if _server is None:
        _server = ForziumHttpServer()
    return _server


def serve(addr: str) -> None:
    """Start the server."""
    server = get_server()
    LOGGER.info("Starting Forzium server on %s", addr)
    server.serve(addr)


def shutdown() -> None:
    """Shutdown the server."""
    global _server
    if _server is not None:
        LOGGER.info("Shutting down Forzium server")
        _server.shutdown()
        _server = None


# For backward compatibility
server = get_server()
