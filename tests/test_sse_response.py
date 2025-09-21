from forzium import ForziumApp
from forzium.responses import EventSourceResponse
from forzium.testclient import TestClient

app = ForziumApp()

@app.get("/events")
def events():
    def gen():
        yield {"event": "greet", "data": "hello"}
        yield {"data": "world"}
    return EventSourceResponse(gen())

def test_event_source_response():
    client = TestClient(app)
    res = client.get("/events")
    assert res.status_code == 200
    assert res.headers["content-type"] == "text/event-stream"
    assert res.text == "event: greet\ndata: hello\n\ndata: world\n\n"