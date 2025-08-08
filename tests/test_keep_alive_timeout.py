"""Verify keep-alive timeout configuration."""

from forzium_engine import ForziumHttpServer


def test_keep_alive_roundtrip() -> None:
    srv = ForziumHttpServer()
    assert srv.get_keep_alive_timeout() == 0
    srv.set_keep_alive_timeout(7)
    assert srv.get_keep_alive_timeout() == 7
