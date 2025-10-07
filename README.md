# ForziumAPI

## Introduction

ForziumAPI is a high-performance API framework that reimplements FastAPI semantics on top of a Rust execution core.  The goal is full contract compatibility with FastAPI while delivering materially lower latency and higher throughput.

Developers continue to author endpoints in Python, but request handling, data validation, and heavy compute live in Rust.  This division eliminates Python’s interpreter overhead for the hot path while keeping the ergonomic decorator API.

ForziumAPI operates in two complementary modes:

- **Library Mode** – import the application and call handlers directly (zero HTTP cost, ideal for internal calls).
- **Server Mode** – run the embedded Rust HTTP server (`forzium_engine::ForziumHttpServer`) that dispatches to Python handlers via PyO3.

The current package version is exported as `forzium.__version__ = "0.1.4"`.

---

## Feature Highlights (v0.1.4)

| Capability | Status | Notes |
| --- | --- | --- |
| Async route handlers | ✅ | Awaited transparently; exceptions reuse shared error handling |
| FastAPI-style validation errors | ✅ | `{"detail": [{"loc", "msg", "type"}]}` payloads for 422 responses |
| Direct `Response` objects | ✅ | Status, headers, background tasks preserved without double encoding |
| Streaming responses | ✅ | `StreamingResponse` and `EventSourceResponse` send chunked bodies incrementally |
| Background tasks | ✅ | Merge with response-bound tasks even for streaming outputs |
| Pydantic v1/v2 request models | ✅ | Parsed through `_coerce_value` with native validation errors |
| Rayon-parallel compute engine | ✅ | Matrix/conv kernels scale across CPU cores |
| Built-in rate limiting | ✅ | Middleware + env config (`FORZIUM_RATE_LIMIT`, `*_WINDOW`, `*_SCOPE`) |
| Observability | ✅ | OpenTelemetry spans, Prometheus metrics, structured request logging |
| CLI workflow | ✅ | `forzium run` auto-loads apps; `forzium new` scaffolds projects; `forzium bench` writes JSON reports |

---

## Using ForziumAPI


### Defining Routes

```python
from typing import Any
from forzium import ForziumApp, Response
from forzium_engine import ForziumHttpServer

server = ForziumHttpServer()
app = ForziumApp(server)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/compute")
def compute(payload: dict[str, Any]) -> Response:
    # Heavy lifting performed in Rust compute engine
    result = run_computation(payload)
    return Response(result, status_code=200)
```

Handlers may be synchronous or `async def`; coroutine return values are awaited automatically.  Background tasks can be injected via `BackgroundTasks` dependencies, and returning `forzium.Response` preserves custom headers, status codes, and binary bodies.

### Running the Server

```python
if __name__ == "__main__":
    server.serve("127.0.0.1:8000")
```

The Rust server owns the socket and dispatches to `_make_handler`.  Shutdown occurs via `server.shutdown()` or SIGINT handling in the CLI.

### Library Mode Usage

The same handlers can be invoked directly without HTTP.  Dependency resolution, validation, and background tasks still apply, making it simple to reuse API logic internally.

### Pydantic & Dataclass Support

Annotating parameters with dataclasses or `pydantic.BaseModel` subclasses triggers structured parsing through `_coerce_value`.  Validation failures yield 422 responses mirroring FastAPI’s schema so existing clients continue to work.

### Streaming Responses

Return `StreamingResponse` or `EventSourceResponse` to stream data chunk-by-chunk.  The Rust server consumes the async iterator, propagates headers, and still executes background tasks when the stream finishes.

### Built-in Rate Limiting

Attach the limiter directly or configure it via environment:

```python
from forzium import RateLimitMiddleware

app.middleware("http")(RateLimitMiddleware(limit=100, window=1.0, scope="client"))
```

Environment variables `FORZIUM_RATE_LIMIT`, `FORZIUM_RATE_LIMIT_WINDOW`, and `FORZIUM_RATE_LIMIT_SCOPE` provide zero-code configuration.  Responses include `429` with `Retry-After` when limits are exceeded.


## Project Structure

* **`core/`** – Business logic and services that consume the Rust compute engine.
* **`forzium/`** – Framework core implementing routing, dependency injection, HTTP utilities, CLI tooling, and middleware.
* **`interfaces/`** – gRPC definitions and shared schema compatibility helpers.
* **`infrastructure/`** – Monitoring instrumentation, OTLP exporters, and deployment assets.
* **`docs/`** – User-facing documentation and guides.
* **`tests/`** – Comprehensive parity, integration, performance, and stress tests.

---

## Processing Pipeline

1. Rust server accepts the request and resolves the Python handler key.
2. OpenTelemetry spans start and Prometheus counters increment.
3. Dependencies resolve (sync or async) via `solve_dependencies`.
4. Bodies are coerced into annotated types (dataclasses, Pydantic models, primitives).
5. Handler executes; coroutine results are awaited automatically.
6. Responses are normalized (streaming, Response objects, or negotiated JSON/text).
7. Background tasks execute asynchronously after the response is dispatched.
8. HTTP/2 push hints and telemetry finalizers run before control returns to Hyper.

---

## Getting Started Quickly

1. Install dependencies: `pip install -r requirements.txt`
2. Start the server: `python run_server.py`
3. Test the API: `curl http://localhost:8000/health`

For detailed usage instructions, see [User Guide](docs/USER_GUIDE.md).

## Documentation

* **[User Guide](docs/USER_GUIDE.md)** - Complete usage guide and examples
* **[Architecture](docs/architecture.md)** - System architecture overview
* **[Performance Baseline](docs/performance_baseline.md)** - Performance benchmarks
* **[Release Notes](docs/release_notes.md)** - Version history and changes
* **[Enterprise Guide](docs/enterprise_adoption_note.md)** - Enterprise deployment guide
