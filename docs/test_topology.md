# Test Topology & Resource Pinning

This document defines the canonical execution environments. 
The goal is deterministic performance measurements through
explicit resource quotas, consistent observability wiring, and reproducible
bootstrapping commands.

## Development (Single-Node) Stack

* **Orchestration**: Docker Compose (`infrastructure/deployment/templates/docker-compose.yml`).
* **Services**:
  * `api` – Forzium application served by the embedded Rust HTTP engine.
  * `redis` – Backing cache and task queue endpoint for tests exercising Redis
    integrations.
  * `otel-collector` – OpenTelemetry Collector exposing OTLP gRPC/HTTP ingress
    and a Prometheus scrape endpoint for metrics exported from traces.
  * `jaeger` – Trace visualization backend receiving OTLP traffic from the
    collector.
  * `prometheus` – Metrics store scraping both the API and the collector.
  * `grafana` – Dashboarding surface pre-provisioned with the repository
    dashboards.
* **Resource Pinning**:
  * `api` – 2 vCPUs limit / 1 vCPU reservation, 2 GiB limit / 1 GiB reservation.
  * `redis` – 0.5 vCPU limit / 0.25 vCPU reservation, 512 MiB limit / 256 MiB
    reservation.
  * `otel-collector` – 1 vCPU limit / 0.25 vCPU reservation, 512 MiB limit /
    256 MiB reservation.
  * `jaeger` – 0.5 vCPU limit / 0.25 vCPU reservation, 512 MiB limit / 256 MiB
    reservation.
  * `prometheus` – 1 vCPU limit / 0.25 vCPU reservation, 1 GiB limit / 512 MiB
    reservation.
  * `grafana` – 0.75 vCPU limit / 0.25 vCPU reservation, 512 MiB limit / 256 MiB
    reservation.
* **Bootstrapping**:
  ```bash
  docker compose \
    -f infrastructure/deployment/templates/docker-compose.yml \
    up --build
  ```
* **Health Gate**: The `api` service exposes `/health`; Grafana dashboards and
  Prometheus targets should report green before measurements begin.

## Staging (Distributed) Stack

* **Orchestration**: Kubernetes Job (`infrastructure/deployment/templates/kubernetes/staging-job.yaml`).
* **Workload**: Forzium smoke test job running the CLI `run` command without
  blocking so that requests can target the pod during validation.
* **Resource Pinning**:
  * CPU requests: 2 vCPU (2000m); limits: 4 vCPU (4000m).
  * Memory requests: 4 GiB; limits: 8 GiB.
  * Ephemeral storage requests: 1 GiB; limits: 4 GiB (for OTLP retry buffer).
* **Node Selection**: Constrained to nodes labeled `forzium.dev/pool=staging-cpu`
  with toleration `forzium.dev/staging` to avoid preemptible pools.
* **Observability Wiring**:
  * OTLP endpoint: `http://otel-collector.staging.svc.cluster.local:4317`.
  * Redis: `redis://forzium-redis.staging.svc.cluster.local:6379/0`.
  * Trace retries persisted to `/var/log/forzium/otlp-retry` via an `emptyDir`
    volume sized to 4 GiB.
* **Deployment**:
  ```bash
  kubectl apply -f infrastructure/deployment/templates/kubernetes/staging-job.yaml
  ```
* **Health Gate**: Readiness probe polls `/health`; only after the pod is ready
  should load or regression suites be pointed at the staging endpoint.

## Operational Notes

* Compose stack binds the API on `localhost:8000`, Prometheus on `:9090`,
  Grafana on `:3000`, and Jaeger UI on `:16686`.
* Grafana auto-loads dashboards from `infrastructure/monitoring/dashboards`;
  modifications should be exported to JSON and checked in to remain in sync.
* Both environments assume the container image tag `0.1.4`; update manifests and
  Compose file when the framework version changes.
* When extending the staging topology with additional workers, duplicate the job
  manifest using unique labels so that Prometheus alert routing remains stable.