use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use std::panic::{catch_unwind, AssertUnwindSafe};
use thiserror::Error;

/// Domain error type for Forzium operations.
#[derive(Debug, Error)]
pub enum ForziumError {
    /// Input validation failed.
    #[error("validation error: {0}")]
    Validation(String),
    /// Computation failed internally.
    #[error("compute error: {0}")]
    Compute(String),
    /// Operation was cancelled before completion.
    #[error("cancelled: {0}")]
    Cancelled(String),
}

impl From<ForziumError> for PyErr {
    fn from(err: ForziumError) -> PyErr {
        match err {
            ForziumError::Validation(msg) => PyValueError::new_err(msg),
            ForziumError::Compute(msg) | ForziumError::Cancelled(msg) => {
                PyRuntimeError::new_err(msg)
            }
        }
    }
}

/// Translate Rust panics into Python exceptions.
pub fn catch_unwind_py<F, R>(f: F) -> PyResult<R>
where
    F: FnOnce() -> PyResult<R>,
{
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(result) => result,
        Err(_) => Err(PyRuntimeError::new_err("rust panic")),
    }
}
