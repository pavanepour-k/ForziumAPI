from forzium.app import ForziumApp


def test_route_decorator_sets_expects_body_false_by_default():
    app = ForziumApp()

    @app.route("GET", "/")
    def handler():
        return {"ok": True}

    assert app.routes[0]["expects_body"] is False