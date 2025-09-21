# Monitoring Artifacts

This directory contains curated observability assets that the CI pipeline packages
as part of the release evidence bundle:

* `dashboards/` – Grafana JSON exports for latency, throughput, background task
  lag, and Rayon worker utilization.
* `captures/` – Static PNG snapshots aligned with the JSON dashboards to support
  offline review by release management and SRE teams.

The assets are versioned with the codebase.  The CI artifact packager copies
these resources into `artifacts/ci/dashboards/` so that every build uploads a
self-contained observability snapshot with a 30-day retention policy.