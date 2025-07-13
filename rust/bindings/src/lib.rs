use forzium::api::{validate_buffer_size, validate_u8_range, validate_utf8_string};
use forzium::errors::ProjectError;
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;

/// Validate buffer size (10MB limit)
#[pyfunction(name = "validate_buffer_size", signature = (data, /))]
#[pyo3(text_signature = "(data, /)")]
fn validate_buffer_size_py(data: &[u8]) -> PyResult<()> {
    validate_buffer_size(data).map_err(|err| match err {
        ProjectError::Validation { message, .. } => PyValueError::new_err(message),
        _ => PyRuntimeError::new_err("Unexpected error"),
    })
}

/// Validate UTF-8 string
#[pyfunction(name = "validate_utf8_string", signature = (data, /))]
#[pyo3(text_signature = "(data, /)")]
fn validate_utf8_string_py(data: &[u8]) -> PyResult<String> {
    validate_utf8_string(data).map_err(|err| match err {
        ProjectError::Validation { message, .. } => PyValueError::new_err(message),
        _ => PyRuntimeError::new_err("Unexpected error"),
    })
}

/// Validate u8 range (0-255)
#[pyfunction(name = "validate_u8_range", signature = (value, /))]
#[pyo3(text_signature = "(value, /)")]
fn validate_u8_range_py(value: u8) -> PyResult<()> {
    validate_u8_range(value).map_err(|err| match err {
        ProjectError::Validation { message, .. } => PyValueError::new_err(message),
        _ => PyRuntimeError::new_err("Unexpected error"),
    })
}

/// MANDATORY: Register all functions with correct module name
#[pymodule]
fn _rust_lib(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_buffer_size_py, m)?)?;
    m.add_function(wrap_pyfunction!(validate_utf8_string_py, m)?)?;
    m.add_function(wrap_pyfunction!(validate_u8_range_py, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
