# Forzium Load Generator WASM Template

This crate is a companion to the Python and k6 harnesses. It provides a
foundation for teams that prefer to drive load from a WebAssembly module (for
example when embedding logic inside k6 extensions or bespoke orchestrators).

## Building

```
cargo build --target wasm32-unknown-unknown --release
```

The resulting artifact under `target/wasm32-unknown-unknown/release` exports two
main primitives:

* `DeterministicRng` – a reproducible random-number generator (LCG) matching the
  Python harness behaviour for payload and tenant sampling.
* `PlanCursor` – an iterator over precomputed schedule entries. Feed it JSON
  produced by `scripts.load_suite` or `load_generators/common.py` and pull
  entries one by one from host environments.

## Extending

1. Generate a plan in Python:
   ```python
   import json
   from pathlib import Path

   from load_generators.common import load_runtime_from_file

   runtime = load_runtime_from_file(Path("scenarios/release_v0_1_4.yaml"), "steady-baseline")
   entries_json = json.dumps([
       {
           "sequence": entry.sequence,
           "offset_s": entry.offset_s,
           "stage": entry.stage,
           "include_in_metrics": entry.include_in_metrics,
       }
       for entry in runtime.plan.entries
   ])
   ```
2. Instantiate `PlanCursor` from WebAssembly hosts and stream entries to your
   networking stack.
3. Use `DeterministicRng` in the host to mirror payload sizing logic if needed.

All exported APIs are annotated with `#[wasm_bindgen]` so they can be consumed
from JavaScript, Rust hosts (via `wasmtime`/`wasmer`), or other ecosystems that
understand WASM interface types.