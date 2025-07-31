//! Bridge for triggering Python's garbage collection from Rust

use pyo3::prelude::*;

/// Force a Python garbage collection cycle.
#[pyfunction]
pub fn force_gc(py: Python<'_>) -> PyResult<()> {
    let gc = py.import("gc")?;
    gc.call_method0("collect")?;
    Ok(())
}
