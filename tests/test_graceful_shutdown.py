"""Ensure shutdown hooks execute during graceful termination."""

import asyncio

from forzium.app import ForziumApp


def test_shutdown_hook_called() -> None:
    app = ForziumApp()
    called: dict[str, bool] = {"flag": False}

    @app.on_event("shutdown")
    def _shutdown() -> None:
        called["flag"] = True

    loop = asyncio.new_event_loop()
    loop.run_until_complete(app.shutdown())
    loop.close()
    assert called["flag"]