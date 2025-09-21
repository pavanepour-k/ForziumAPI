# PyO3 Boundary Overhead Microbenchmark

## Audience

Runtime performance engineers and the ForziumAPI core maintainers who need quantitative evidence of PyO3 call boundary costs when Python dispatches into the Rust execution core.

## Objectives

* Measure the steady-state latency overhead of invoking lightweight Rust functions from Python through PyO3.
* Provide a reproducible harness and captured dataset for regression tracking.
* Highlight relative cost compared to equivalent pure-Python call paths to guide optimization work.

## Methodology

| Aspect | Detail |
| --- | --- |
| Harness | `scripts/run_pyo3_boundary_bench.py` (new CLI microbenchmark) |
| Invocation counts | 10,000 warm-up calls per case followed by 15 timed repeats of 100,000 invocations each |
| Timing source | `time.perf_counter()` inside the harness with aggregation via `statistics.fmean` / `statistics.stdev` |
| Hardware/OS | Linux kernel 6.12.13 (containerized CI image) |
| Python runtime | CPython 3.12.10 inside project-managed virtualenv (`.venv`) |
| Rust module build | `maturin develop --release` targeting the `forzium_engine` crate |
| Functions benchmarked | Baseline Python increment, Python no-op, Rust `noop` (zero-arg), Rust `echo_u64` (single integer parameter round-trip) |
| Result artifact | `metrics/pyo3_boundary_overhead.json` (committed) |

All benchmark cases execute inside a single Python process with the GIL held. Warm-ups retire interpreter caches and PyO3 initialization overhead before the timed loops begin. Each result captures the raw duration per repeat, the mean per-call latency (in nanoseconds), standard deviation, and derived calls-per-second throughput. Relative factors are normalized against the Python increment baseline.

## Results Summary

| Case | Mean latency (ns/call) | Std dev (ns) | Calls/sec (M) | Relative to Python increment |
| --- | ---:| ---:| ---:| ---:|
| Python increment baseline | 80.08 | 0.77 | 12.49 | 1.00× |
| Python no-op | 70.71 | 1.45 | 14.14 | 0.88× |
| Rust `noop()` via PyO3 | 71.43 | 0.82 | 14.00 | 0.89× |
| Rust `echo_u64(0)` via PyO3 | 88.35 | 3.66 | 11.32 | 1.10× |

Key observations:

1. The zero-argument Rust entrypoint delivers **≈14.0 million calls/second**, practically indistinguishable from the pure-Python no-op cost. The PyO3 bridge adds ~0.7 ns over the Python no-op measurement, which sits well within CPython dispatch noise.
2. Crossing the boundary with integer argument marshaling (`echo_u64`) costs ~88 ns/call, a **10% premium** over the Python increment baseline. That delta represents argument boxing/unboxing and Rust↔Python conversion costs.
3. Variance across repeats stays below 4.2% relative standard deviation, indicating a stable measurement regime suitable for regression gating.

## Operational Guidance

* Integrate the new CLI into CI/CD to track regressions: `python scripts/run_pyo3_boundary_bench.py --output metrics/pyo3_boundary_overhead.json`.  
* When comparing alternative PyO3 strategies (e.g., zero-copy buffers or `PyObject` passthrough), reuse this harness to quantify improvements against the committed dataset.  
* Combine per-call latency with workload-specific call counts to estimate total PyO3 cost within end-to-end scenarios.  
* Maintain the `.venv` environment and rebuild the Rust crate (`maturin develop --release`) before rerunning the benchmark to ensure symbol availability and reproducible linking.

## Artifact Index

* Benchmark harness source: `scripts/run_pyo3_boundary_bench.py`
* Captured dataset: `metrics/pyo3_boundary_overhead.json`
* Supporting Rust entrypoints: `core/rust_engine/src/lib.rs` (`noop`, `echo_u64`)