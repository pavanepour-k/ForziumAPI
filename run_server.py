"""Run the Forzium application using the Rust HTTP server."""

import argparse
import logging
import os
import time

from core import server

LOGGER = logging.getLogger("forzium.server")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Forzium server")
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host interface to bind",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port number to listen on",
    )
    args = parser.parse_args()
    server.serve(f"{args.host}:{args.port}")
    LOGGER.info("Forzium server running on %s:%s", args.host, args.port)
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
