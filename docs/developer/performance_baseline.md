# Performance Baseline

## Scenario

- **Route:** `/baseline`
- **Total Requests:** 1,200 per run
- **Concurrency:** 12 worker threads per run
- **Runs:** 3 consecutive executions using `scripts/performance_baseline.py`
- **Environment:** In-process `TestClient` with stubbed `forzium_engine` bindings (no external I/O)

## Metrics Captured

Each run records:

- End-to-end duration (seconds)
- Throughput (requests per second)
- Latency distribution (mean, median, p95, p99, max in milliseconds)
- Error counts and derived error rate

## Aggregate Results

| Metric | Mean | Min | Max |
| --- | --- | --- | --- |
| Throughput (rps) | 2,200.55 | 2,076.58 | 2,306.24 |
| Duration (s) | 0.546 | 0.520 | 0.578 |
| Latency mean (ms) | 3.63 | — | — |
| Latency p95 (ms) | 21.14 | — | — |
| Error rate | 0.0 | — | — |

Refer to [`metrics/performance_baseline.json`](../metrics/performance_baseline.json) for per-run details.

## δ Policy

- Throughput must not fall more than **5%** below the recorded baseline mean.
- P95 latency must not exceed the baseline by more than **10%**.
- Error rate must remain **0** (no allowance for regressions).

## Regeneration Procedure

1. Ensure `forzium_engine` is available (or allow the script to use its stub).
2. Run:
   ```bash
   python scripts/performance_baseline.py --print
   ```
3. Commit the updated `metrics/performance_baseline.json` and adjust `metadata.generated_at` in `gating.yaml`.

The script ensures reproducibility by distributing requests evenly across worker threads and capturing per-request latency samples for percentile computation.
