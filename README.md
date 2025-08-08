# Forzium

Forzium is a FastAPI-compatible framework powered by a Rust core.
Current status: **pre-v0.1.0** (development).
See `docs/release_notes.md` for draft notes.
It ships with a native Rust HTTP server, and routes are registered via
Forzium's decorator-based API. Pydantic sits behind a thin facade while
a custom ASGI app with startup/shutdown events manages lifecycle needs.
WebSockets, sessions, templates, a test client, and authentication
helpers are provided natively. Request and response middleware hooks are
available. Lightweight Request and Response classes handle headers,
cookies, and background tasks, and a simple `Depends` helper enables
basic dependency injection.

## Features

### FastAPI-Compatible Core

- Rust HTTP server with decorator-based routing, typed path parameters, and query handling
- Automatic OpenAPI schema generation and interactive docs at `/docs` and `/redoc`
- Request/Response classes with JSON, form, file parsing, cookies, and background tasks
- Dependency injection via `Depends` and background task utilities
- Session management through signed cookies and file-backed stores
- Template rendering and response helpers for JSON, HTML, files, and streams
- WebSocket routes with in-memory channels
- Middleware support including CORS, GZip, HTTPS redirect, and TrustedHost
- TestClient for in-process request testing

### Optional Forzium Plugins(TODO)

- HTTP/2 server push helpers
- Prometheus metrics endpoint
- CLI with dynamic plugin system
- RBAC and JWT utilities backed by SQLite
- gRPC computation interface with health checks
- GPU-accelerated tensor operations
- WebSocket broadcast channels and clustering

## Example

```python
from forzium import ForziumApp

app = ForziumApp()

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

## Installation

```bash
pip install .
```

## Running

```bash
python run_server.py
```

This launches the bundled Rust HTTP server. It listens on
`0.0.0.0:8000` by default, allowing access from outside the container
when the port is exposed. It supports dynamic path parameters, allowing
routes such as `/items/{id:int}` to be registered and handled natively.
Interactive documentation is served at `/docs` (Swagger UI) and
`/redoc` (ReDoc).

## Cancellation and Memory Model

Long-running operations may be aborted using
``CancellationToken`` objects passed to computation helpers. Memory is
managed by a variable-size ``PoolAllocator`` allowing zero-copy buffer
sharing across the Rust/Python FFI boundary while keeping peak usage
below 500 MB under benchmark workloads.

## Testing and HTTP Primitives

The ``TestClient`` issues requests directly against a ``ForziumApp``
without a network stack. Responses expose ``json`` helpers and header
access. The ``Request`` and ``Response`` classes provide cookie and
background task management, while the ``TemplateRenderer`` renders simple
``str.format`` templates from disk.

## GPU Acceleration

Matrix helpers in ``core.service.gpu`` call custom CUDA kernels when
``FORZIUM_USE_GPU=1``. Set ``FORZIUM_GPU_DEVICE`` to select which GPU
device runs the kernels; CPU paths delegate to the Rust engine.

## Session Management

Forzium ships with two session options. ``SessionMiddleware`` stores all
data client side in a signed cookie. ``FileSessionMiddleware`` keeps a
server-side JSON file of session state referenced by an identifier in the
cookie. The latter allows persistent sessions across restarts at the
cost of disk I/O.

## Docker

```bash
docker build -t forzium .
docker run -p 8000:8000 forzium
```

## Pipeline

To run all checks locally, execute:

```bash
python build_pipeline.py
```

Continuous integration runs the same suite via
`.github/workflows/auto-ci.yml`. Each push triggers ruff, flake8, mypy,
`cargo fmt --check`, the unit tests, and the performance benchmark.

To view a coverage report, run:

```bash
poetry run pytest
```

Coverage statistics are printed after the test summary.

See `scripts/README.md` for additional development scripts.

## gRPC Interface

Start a gRPC server exposing computation endpoints:

```python
from interfaces.grpc import start_grpc_server
server = start_grpc_server()
```

The server also exposes the gRPC health checking service on the same
port.

## Monitoring

Failed OTLP exports are written to disk when a buffering directory is
configured. Stored batches can be resent via ``forzium replay-otlp``.
The replay service can be auto-started on app startup; configure the
interval via ``FORZIUM_REPLAY_INTERVAL``.

## RBAC Storage

Role definitions, assignments, and audit logs persist to a SQLite
database specified by ``FORZIUM_RBAC_DB``.
RBAC HTTP endpoints require a JWT signed with ``FORZIUM_SECRET`` and the
``rbac`` scope.

## Security Schemes

Forzium provides helpers for OAuth2 flows, HTTP Basic/Bearer auth, and API
keys. The ``forzium.auth`` module exposes utilities to parse Authorization
headers, retrieve API keys from headers, query parameters, or cookies, and
issue JWTs for password, client credentials, authorization code, and
implicit flows.
