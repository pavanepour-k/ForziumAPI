from forzium import ForziumApp
from forzium.dependency import Depends
from forzium.testclient import TestClient


def test_mount_dependency_scoping():
    def dep():
        return "orig"

    def override():
        return "override"

    sub = ForziumApp()

    @sub.get("/item")
    def item(val: str = Depends(dep)):
        return {"v": val}

    app = ForziumApp()
    app.mount("/sub", sub)

    client = TestClient(app)
    assert client.get("/sub/item").json() == {"v": "orig"}

    app.dependency_overrides[dep] = override
    assert client.get("/sub/item").json() == {"v": "orig"}

    sub.dependency_overrides[dep] = override
    assert client.get("/sub/item").json() == {"v": "override"}