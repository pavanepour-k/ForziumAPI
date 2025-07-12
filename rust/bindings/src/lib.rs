use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PyRuntimeError, PyTypeError, PyNotFoundError};
use pyo3::types::{PyBytes, PyType, PyAny};
use project_core::api;
use project_core::errors::ProjectError;

/// FastAPI Core FFI Bindings (auto-generated).
/// 
/// Example:
///     process_data(b"input", validate=True)
///
/// Returns:
///     bytes -- processed result
///
/// Raises:
///     ValueError -- input validation error
///     RuntimeError -- processing/panic error
#[pyfunction(name = "validate_buffer", signature = (data, /))]
#[pyo3(text_signature = "(data, /)")]
fn validate_buffer_py(data: &PyAny) -> PyResult<()> {
    let bytes: Vec<u8> = match data.extract() {
        Ok(b) => b,
        Err(_) => return Err(PyTypeError::new_err("Input must be bytes")),
    };
    api::validate_buffer_size(&bytes).map_err(|err| match err {
        ProjectError::Validation{message, ..} => PyValueError::new_err(message),
        _ => PyRuntimeError::new_err("Unexpected error"),
    })
}

#[pyfunction(name = "validate_utf8", signature = (data, /))]
#[pyo3(text_signature = "(data, /)")]
fn validate_utf8_py(data: &PyAny) -> PyResult<String> {
    let bytes: Vec<u8> = data.extract().map_err(|_| PyTypeError::new_err("Input must be bytes"))?;
    api::validate_utf8_string(&bytes).map_err(|err| match err {
        ProjectError::Validation{message, ..} => PyValueError::new_err(message),
        _ => PyRuntimeError::new_err("Unexpected error"),
    })
}


fn wrap_panic<F, T>(py: Python, f: F) -> PyResult<T>
where
    F: FnOnce() -> PyResult<T> + std::panic::UnwindSafe
{
    py.allow_threads(move || {
        std::panic::catch_unwind(f)
            .unwrap_or_else(|_| Err(PyRuntimeError::new_err("Rust panic occurred")))
    })?
}

#[pymodule]
fn _rust_core_bindings(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_buffer_py, m)?)?;
    m.add_function(wrap_pyfunction!(validate_utf8_py, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
