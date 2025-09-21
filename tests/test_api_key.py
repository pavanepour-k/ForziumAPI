# flake8: noqa
from typing import Annotated

from forzium import Depends, ForziumApp
from forzium.security import api_key_query
from forzium.testclient import TestClient


def test_api_key_query_protection() -> None:
    app = ForziumApp()
    app.add_security_scheme(
        "ApiKey", {"type": "apiKey", "in": "query", "name": "api_key"}
    )

    @app.get("/secure-data")
    def secure_data(
        api_key: str = Depends(api_key_query),  # type: ignore[assignment]
    ) -> dict[str, str]:
        return {"message": "secured"}

    client = TestClient(app)
    ok = client.get("/secure-data", params={"api_key": "secret"})
    assert ok.status_code == 200
    assert ok.json() == {"message": "secured"}

    unauthorized = client.get("/secure-data")
    assert unauthorized.status_code == 401