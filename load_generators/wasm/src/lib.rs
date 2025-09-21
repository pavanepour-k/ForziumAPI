//! Deterministic ForziumAPI load-scheduling primitives for WASM hosts.
//!
//! This template mirrors the behaviour of the Python harness exposed in
//! `load_generators/common.py`.  It allows hosts such as k6 or bespoke Rust
//! runners to iterate through an execution plan generated offline (e.g. via
//! `scripts.load_suite`) while staying fully deterministic.

use serde::{Deserialize, Serialize};
use wasm_bindgen::prelude::*;

/// Single scheduled request entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleEntry {
    /// Monotonic sequence identifier.
    pub sequence: u32,
    /// Offset from the start of the scenario in seconds.
    pub offset_s: f64,
    /// Stage label (e.g. `steady`, `burst-1`).
    pub stage: String,
    /// Whether the request should be included in metrics aggregation.
    pub include_in_metrics: bool,
}

/// Deterministic linear congruential generator.
#[wasm_bindgen]
pub struct DeterministicRng {
    state: u64,
}

#[wasm_bindgen]
impl DeterministicRng {
    /// Create a new RNG seeded by `seed`.
    #[wasm_bindgen(constructor)]
    pub fn new(seed: u64) -> DeterministicRng {
        let seed = if seed == 0 { 0x6d_2b_79_f5 } else { seed };
        DeterministicRng { state: seed }
    }

    /// Return the next pseudo-random `f64` in `[0, 1)`.
    pub fn next_f64(&mut self) -> f64 {
        self.state = self
            .state
            .wrapping_mul(636_413_622_384_679_3005)
            .wrapping_add(1);
        ((self.state >> 33) as f64) / (1u64 << 31) as f64
    }

    /// Sample an exponential variate with rate `lambda`.
    pub fn expovariate(&mut self, lambda: f64) -> f64 {
        if lambda <= 0.0 {
            return 0.0;
        }
        let u = self.next_f64().max(f64::EPSILON);
        -u.ln() / lambda
    }
}

/// Iterator over a pre-computed plan.
#[wasm_bindgen]
pub struct PlanCursor {
    entries: Vec<ScheduleEntry>,
    index: usize,
}

#[wasm_bindgen]
impl PlanCursor {
    /// Construct a plan cursor from a JSON array of [`ScheduleEntry`].
    #[wasm_bindgen(constructor)]
    pub fn new(plan_json: &str) -> Result<PlanCursor, JsValue> {
        let entries: Vec<ScheduleEntry> = serde_json::from_str(plan_json)
            .map_err(|err| JsValue::from_str(&format!("failed to parse plan: {err}")))?;
        Ok(PlanCursor { entries, index: 0 })
    }

    /// Reset the cursor to the first entry.
    pub fn reset(&mut self) {
        self.index = 0;
    }

    /// Remaining scheduled requests.
    pub fn remaining(&self) -> u32 {
        self.entries.len().saturating_sub(self.index) as u32
    }

    /// Return the next entry as a JSON value or `null` when exhausted.
    pub fn next(&mut self) -> JsValue {
        if let Some(entry) = self.entries.get(self.index) {
            self.index += 1;
            JsValue::from_serde(entry).unwrap_or(JsValue::NULL)
        } else {
            JsValue::NULL
        }
    }
}

/// Helper that converts a `ScheduleEntry` slice into JSON for transport.
#[wasm_bindgen]
pub fn serialise_plan(entries: JsValue) -> Result<String, JsValue> {
    let schedule: Vec<ScheduleEntry> = entries
        .into_serde()
        .map_err(|err| JsValue::from_str(&format!("invalid plan entries: {err}")))?;
    serde_json::to_string(&schedule).map_err(|err| JsValue::from_str(&err.to_string()))
}
