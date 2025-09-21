# ForziumAPI Architecture

## System Overview
ForziumAPI pairs a high-performance Rust execution core with a Python developer surface that mirrors FastAPI.  The platform exposes identical routing and dependency semantics to FastAPI while delegating HTTP parsing, validation, and compute-intensive work to the Rust engine.  Two execution topologies are supported:

* **Server mode** – `forzium_engine::ForziumHttpServer` (Axum/Hyper based) owns the socket, converts HTTP traffic into lightweight Rust structures, and invokes Python handlers through PyO3 shims.
* **Library mode** – applications import `forzium.ForziumApp` directly.  Routes behave like regular callables so internal services can execute business logic without touching the network stack.

Regardless of topology, the Rust engine is responsible for request normalization, dispatch scheduling, telemetry, and background task orchestration.  Python keeps ownership of ergonomics (decorators, dependency injection, middlewares) while shipping work back to Rust using zero-copy buffers where possible.

## Layered Components

| Layer | Responsibility | Key Modules |
| --- | --- | --- |
| **Rust Core** | HTTP server, async runtime, request routing, compute kernels accelerated with Rayon | `core/rust_engine/src/server`, `core/rust_engine/src/compute`, `forzium_engine` binding |
| **Python Surface** | Routing decorators, dependency graph solving, type coercion, response serialization | `forzium/app.py`, `forzium/dependency.py`, `forzium/http.py` |
| **Domain Services** | Business workflows and GPU extensions | `core/service`, `core/app.py` |
| **Interfaces** | gRPC gateway, shared schemas, Pydantic compatibility glue | `interfaces/grpc`, `interfaces/pydantic_compat.py` |
| **Infrastructure** | Observability, configuration, deployment scripts | `infrastructure/monitoring`, `scripts/`, `_docs/` |

Each layer exposes narrow contracts to the one above it.  The Rust layer surfaces a minimal ABI (`ForziumHttpServer`, `forzium_engine.compute`) so that Python can remain pure application logic while benefiting from Rust’s concurrency.

## Request Lifecycle

1. **Socket accept (Rust)** – Hyper accepts the TCP stream.  The router computes the Python handler key.
2. **Span bootstrap** – `infrastructure.monitoring.start_span` records an OpenTelemetry span for the request.  Metrics counters (`prometheus_metrics`) capture throughput and latency buckets.
3. **Parameter extraction** – path, query, and header values are parsed on the Rust side and transferred to Python as primitives.  Request bodies stream through a bounded buffer respecting `max_upload_size`.
4. **Dependency resolution (Python)** – `solve_dependencies` walks the dependency graph, instantiating context managers and injecting `Request`, `BackgroundTasks`, or user dependencies.  Async dependencies are awaited transparently.
5. **Type coercion** – `_coerce_value` converts JSON payloads into dataclasses, Pydantic models, or annotated primitives.  Validation issues raise `RequestValidationError` objects that map to FastAPI-style `{"detail": [{"loc": ..., "msg": ..., "type": ...}]}` payloads.
6. **Handler execution** – regular functions execute synchronously; coroutine handlers are awaited via `asyncio.run` so `async def` routes behave exactly like FastAPI.
7. **Response normalization** – results can be:
   * `forzium.dependency.Response` instances (status, headers, body preserved, background tasks executed),
   * `StreamingResponse` / `EventSourceResponse` generators sending chunked bodies incrementally,
   * raw values encoded according to `Accept` negotiation (`application/json`, `text/plain`).
8. **Background work** – `BackgroundTasks` merge with response-bound tasks.  Execution occurs on a detached thread scheduling into `asyncio` to avoid blocking the Rust runtime.
9. **Finalization** – response hooks, HTTP/2 push hints, and telemetry exporters run.  Control returns to Hyper which writes the response.

## Asynchronous and Streaming Semantics

* **Async routes** – `_make_handler` recognizes awaitables, awaits them, and propagates exceptions through the shared error mappers.  Validation errors from `async def` routes leverage the same 422 structure.
* **Streaming** – returning `StreamingResponse` yields a lazy iterator consumed chunk-by-chunk by the Rust server, enabling large datasets (10k+ rows) without buffering.  Head requests return metadata only.
* **Background tasks** – both middleware-injected and handler-specified tasks run even for streaming results because `StreamingResponse.background` merges with pending tasks.

## Observability Stack

* Request spans include attributes for HTTP method, path, status, duration, and handler name.
* Sub-spans wrap validation and handler execution for fine-grained timing.
* Metrics are exported through Prometheus collectors and can be scraped alongside OTLP traces.
* Structured logging middleware records method, path, status, response time, and rate-limit counters when enabled.

## Configuration & Middleware

* Rate limiting is configurable via `FORZIUM_RATE_LIMIT`, `FORZIUM_RATE_LIMIT_WINDOW`, and `FORZIUM_RATE_LIMIT_SCOPE` environment variables or directly through `RateLimitMiddleware`.
* Additional middleware (CORS, GZip, security headers) are applied using the same decorator semantics as FastAPI.
* HTTP/2 server push can be controlled via response hooks registered on the application.

## Data & Compute Engine

* Matrix and convolution operations inside `core/rust_engine` use Rayon to parallelize loops across CPU cores.
* GPU paths (`core/service/gpu`) fallback gracefully when CUDA is unavailable.
* Validation rules can be extended on the Rust side and exposed to Python via the ABI for zero-copy enforcement.

## Deployment Model

* `forzium.cli` ships `forzium run` and `forzium new` commands to simplify developer workflows.
* Dockerfiles in the template scaffold use multi-stage builds with `maturin` to produce slim images.

For end-to-end parity with FastAPI the documentation set below (migration, quickstart, release notes) should be consulted together with this architecture overview.