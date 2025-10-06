# Rayon Thread Pool Utilization Study

## Overview

This document summarizes the instrumentation added to the Rust compute engine to observe Rayon
thread pool behavior and the baseline utilization measurements captured for the v0.1.4 runtime.

## Instrumentation

- Added a `rayon_metrics` module that records:
  - Worker activation counts and high-water marks.
  - Total task executions and aggregate busy time.
  - Per-task duration extrema and derived averages.
- Metrics are exposed to Python through the `forzium_engine.rayon_pool_metrics(reset: bool)`
  function, returning structured telemetry for integration with the broader observability stack.
- A reusable guard (`track_task`) is injected at the outer parallel iteration boundaries of the
  tensor kernels to avoid per-element overhead while accurately reflecting work-stealing activity.

## Collection Methodology

1. Reset the instrumentation counters via the Rust API.
2. Execute a representative workload using the bundled collector binary:
   - Four dense `matmul` calls on 128×128 matrices.
   - Element-wise addition and Hadamard product on matching matrices.
   - A 5×5 convolution over a 96×96 tensor.
   - `max_pool2d` with a stride of four on a 128×128 tensor.
3. Snapshot metrics and persist them to `metrics/rayon_pool_utilization.json`.

The collector lives at `core/rust_engine/src/bin/rayon_metrics_collect.rs` and can be re-run to
refresh the dataset as optimizations land.

## Summary of Results

| Metric | Value |
| --- | --- |
| Observed worker threads | 4 |
| Peak active workers | 5 |
| Mean active workers | 3.58 |
| Average utilization | 89.44% |
| Tasks executed | 892 |
| Mean task duration | 309.19 µs |
| Max task duration | 1.10 ms |
| Min task duration | 8.40 µs |
| Aggregate busy time | 0.276 s |
| Observation window | 0.077 s |

## Interpretation

- **High average utilization (≈89%)** indicates the kernels keep Rayon saturated during the workload.
- **Peak saturation of 1.25** highlights opportunistic over-subscription from nested parallelism,
  validating that the guard placement captures cross-task work stealing.
- **Task duration spread** (8.40 µs – 1.10 ms) aligns with mixed kernels (element-wise vs. matmul),
  offering input for future work-size balancing heuristics.

The dataset and module provide the baseline for regression tracking and
surfacing of Rayon pool inefficiencies in future releases.