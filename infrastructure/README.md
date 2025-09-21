# Infrastructure

This package groups deployment and monitoring utilities.

- `configuration/` holds config loaders and settings.
- `deployment/` contains container and orchestration helpers.
  - `deployment/dev/` provides the multi-stage Dockerfile and runtime
    requirements used by the developer Docker Compose stack.
  - `deployment/templates/docker-compose.yml` wires the API, Redis,
    OpenTelemetry collector, Jaeger, Prometheus, and Grafana with explicit
    CPU/RAM reservations for repeatable single-node testing.
  - `deployment/templates/kubernetes/` ships staging-ready manifests,
    including the resource-pinned `staging-job.yaml` for smoke runs.
- `monitoring/` includes telemetry exporters and replay services.

Refer to `docs/test_topology.md` for full topology diagrams, resource
quotas, and operational guidance for both development and staging tiers.