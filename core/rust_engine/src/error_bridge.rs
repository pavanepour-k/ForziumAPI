use crate::error::ForziumError;
use once_cell::sync::Lazy;
use pyo3::exceptions::{
    PyException, PyMemoryError, PyNotImplementedError, PyReferenceError, PyResourceWarning,
    PyRuntimeError, PyTimeoutError, PyValueError,
};
use pyo3::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};

/// Controls whether detailed error information is included in Python exceptions.
static VERBOSE_ERRORS: AtomicBool = AtomicBool::new(true);

/// Controls whether error stack traces are captured and included in Python exceptions.
static CAPTURE_STACK_TRACES: AtomicBool = AtomicBool::new(true);

/// Stores the last error message for debugging purposes.
pub static LAST_ERROR: Lazy<parking_lot::RwLock<String>> =
    Lazy::new(|| parking_lot::RwLock::new(String::new()));

/// Python exception type for Forzium API errors.
#[pyclass(extends=PyException)]
pub struct PyForziumError {
    #[pyo3(get)]
    code: u32,
    #[pyo3(get)]
    category: String,
    #[pyo3(get)]
    details: Option<String>,
}

/// Set detailed error information mode.
#[pyfunction]
pub fn set_verbose_errors(enabled: bool) -> bool {
    VERBOSE_ERRORS.swap(enabled, Ordering::SeqCst)
}

/// Set stack trace capture mode.
#[pyfunction]
pub fn set_capture_stack_traces(enabled: bool) -> bool {
    CAPTURE_STACK_TRACES.swap(enabled, Ordering::SeqCst)
}

/// Get the last error message.
#[pyfunction]
pub fn get_last_error() -> String {
    LAST_ERROR.read().clone()
}

/// Create a Python exception from a Rust error with enhanced details.
pub fn create_py_error(err: ForziumError) -> PyErr {
    // Store the error message for debugging
    let message = err.to_string();
    *LAST_ERROR.write() = message.clone();

    // Extract error code and category
    let (_code, _category) = match &err {
        ForziumError::Validation(_) => (1000, "validation"),
        ForziumError::Compute(_) => (2000, "compute"),
        ForziumError::Cancelled(_) => (3000, "cancelled"),
        ForziumError::ResourceLimit(_) => (4000, "resource_limit"),
    };

    // Determine if we should include detailed information
    let _details = if VERBOSE_ERRORS.load(Ordering::Relaxed) {
        Some(message.clone())
    } else {
        None
    };

    // Choose appropriate exception type based on error category
    match &err {
        ForziumError::Validation(_) => PyValueError::new_err(message.clone()),
        ForziumError::ResourceLimit(_) => PyResourceWarning::new_err(message.clone()),
        ForziumError::Cancelled(_) => PyTimeoutError::new_err(message.clone()),
        ForziumError::Compute(_) => PyRuntimeError::new_err(message),
    }
}

/// Improved implementation of From<ForziumError> for PyErr
impl From<ForziumError> for PyErr {
    fn from(err: ForziumError) -> PyErr {
        create_py_error(err)
    }
}

/// Wrapper for catching panics and returning enhanced Python exceptions.
pub fn catch_and_convert<F, R>(f: F) -> PyResult<R>
where
    F: FnOnce() -> Result<R, ForziumError>,
{
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)) {
        Ok(Ok(result)) => Ok(result),
        Ok(Err(err)) => Err(create_py_error(err)),
        Err(panic) => {
            let panic_msg = if let Some(s) = panic.downcast_ref::<&str>() {
                s.to_string()
            } else if let Some(s) = panic.downcast_ref::<String>() {
                s.clone()
            } else {
                "Unknown panic occurred".to_string()
            };

            *LAST_ERROR.write() = format!("Rust panic: {}", panic_msg);
            Err(PyRuntimeError::new_err(format!(
                "Rust panic: {}",
                panic_msg
            )))
        }
    }
}

/// Error category enum for Python error classification.
#[pyclass]
#[derive(Clone, Copy, Debug)]
pub enum ErrorCategory {
    #[pyo3(name = "VALIDATION")]
    Validation = 1000,
    #[pyo3(name = "COMPUTE")]
    Compute = 2000,
    #[pyo3(name = "CANCELLED")]
    Cancelled = 3000,
    #[pyo3(name = "RESOURCE_LIMIT")]
    ResourceLimit = 4000,
}

/// Register the error bridge module with Python.
pub fn register(py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    let error_module = PyModule::new_bound(py, "errors")?;
    error_module.add_function(wrap_pyfunction!(
        set_verbose_errors,
        error_module.as_borrowed()
    )?)?;
    error_module.add_function(wrap_pyfunction!(
        set_capture_stack_traces,
        error_module.as_borrowed()
    )?)?;
    error_module.add_function(wrap_pyfunction!(
        get_last_error,
        error_module.as_borrowed()
    )?)?;
    error_module.add_class::<ErrorCategory>()?;
    m.add_submodule(error_module.as_borrowed())?;
    Ok(())
}
