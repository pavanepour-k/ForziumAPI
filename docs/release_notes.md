# ForziumAPI Release Notes

## v0.1.4 (Current)
- Added coroutine-aware handler execution so `async def` routes are awaited automatically.
- Normalized handling for `forzium.dependency.Response` and Starlette-compatible response classes, including background tasks.
- Implemented FastAPI-style validation error payloads with `loc`, `msg`, and `type` fields.
- Delivered true streaming responses via `StreamingResponse`/`EventSourceResponse` with background task propagation.
- Parallelized compute kernels (matrix multiply, convolution) using Rayon for multi-core scaling.
- Introduced built-in rate limiting middleware configurable through environment variables or explicit registration.
- Expanded observability with OpenTelemetry spans and structured request logging middleware.
- Updated documentation set (architecture, migration guide, example app) to reflect parity status.

## v0.1.3
- Hardened dependency resolution for nested context managers and async dependencies.
- Added HTTP/2 server-push helpers and extended middleware hooks for request/response mutation.
- Improved CLI ergonomics in preparation for the `forzium run` workflow.

## v0.1.2
- Stabilized GPU acceleration fallbacks and added benchmark automation scripts.
- Integrated Prometheus metrics exporter and baseline dashboards.
- Documented security compliance workflows and sanitizer coverage expectations.

## v0.1.1
- Initial public preview aligned with FastAPI routing/dependency contracts.
- Established OpenAPI generation, background tasks, and gRPC gateway scaffolding.
- Published internal release processes, benchmarking strategy, and developer roles.

The Python package exports the version constant as `forzium.__version__ = "0.1.4"`.  Downstream projects should track this value when pinning dependencies or generating compatibility matrices.