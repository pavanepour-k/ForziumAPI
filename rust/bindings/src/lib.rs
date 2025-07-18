mod dependencies;
mod request;
mod response;
mod routing;
mod validation;

use forzium::api::{validate_buffer_size, validate_u8_range, validate_utf8_string};
use forzium::errors::ProjectError;
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use routing::PyRouteMatcher;
use std::panic;
use std::sync::atomic::{AtomicU64, Ordering};

// Global object counter for lifetime tracking
static OBJECT_COUNTER: AtomicU64 = AtomicU64::new(0);

// Export safety utilities for other modules
pub(crate) use catch_panic;

/// Catch Rust panics and convert them to Python exceptions
fn catch_panic<F, R>(f: F) -> PyResult<R>
where
    F: FnOnce() -> PyResult<R> + panic::UnwindSafe,
{
    match panic::catch_unwind(f) {
        Ok(result) => result,
        Err(panic_info) => {
            let msg = if let Some(s) = panic_info.downcast_ref::<String>() {
                format!("Rust panic occurred: {}", s)
            } else if let Some(s) = panic_info.downcast_ref::<&str>() {
                format!("Rust panic occurred: {}", s)
            } else {
                "Rust panic occurred: unknown error".to_string()
            };
            Err(PyRuntimeError::new_err(msg))
        }
    }
}

/// Validate buffer size (10MB limit) with panic safety
#[pyfunction(name = "validate_buffer_size", signature = (data, /))]
#[pyo3(text_signature = "(data, /)")]
fn validate_buffer_size_py(data: &[u8]) -> PyResult<()> {
    catch_panic(|| {
        // Validate input bounds to prevent overflow
        if data.len() > usize::MAX / 2 {
            return Err(PyValueError::new_err("Buffer too large for processing"));
        }

        // Log for debugging (only in debug builds)
        #[cfg(debug_assertions)]
        {
            let id = OBJECT_COUNTER.fetch_add(1, Ordering::SeqCst);
            log::debug!("validate_buffer_size call {}: {} bytes", id, data.len());
        }

        validate_buffer_size(data).map_err(|err| match err {
            ProjectError::Validation { message, .. } => PyValueError::new_err(message),
            _ => PyRuntimeError::new_err(format!("Unexpected error: {}", err)),
        })
    })
}

/// Validate UTF-8 string with panic safety
#[pyfunction(name = "validate_utf8_string", signature = (data, /))]
#[pyo3(text_signature = "(data, /)")]
fn validate_utf8_string_py(data: &[u8]) -> PyResult<String> {
    catch_panic(|| {
        // Pre-validate data length
        if data.is_empty() {
            return Ok(String::new());
        }

        if data.len() > 10_485_760 {
            // 10MB limit
            return Err(PyValueError::new_err(
                "Input data exceeds maximum allowed size",
            ));
        }

        #[cfg(debug_assertions)]
        {
            let id = OBJECT_COUNTER.fetch_add(1, Ordering::SeqCst);
            log::debug!("validate_utf8_string call {}: {} bytes", id, data.len());
        }

        validate_utf8_string(data).map_err(|err| match err {
            ProjectError::Validation { message, .. } => PyValueError::new_err(message),
            _ => PyRuntimeError::new_err(format!("Unexpected error: {}", err)),
        })
    })
}

/// Validate u8 range (0-255) with panic safety
#[pyfunction(name = "validate_u8_range", signature = (value, /))]
#[pyo3(text_signature = "(value, /)")]
fn validate_u8_range_py(value: u8) -> PyResult<()> {
    catch_panic(|| {
        #[cfg(debug_assertions)]
        {
            let id = OBJECT_COUNTER.fetch_add(1, Ordering::SeqCst);
            log::debug!("validate_u8_range call {}: value={}", id, value);
        }

        validate_u8_range(value).map_err(|err| match err {
            ProjectError::Validation { message, .. } => PyValueError::new_err(message),
            _ => PyRuntimeError::new_err(format!("Unexpected error: {}", err)),
        })
    })
}

/// MANDATORY: Register all functions with correct module name
#[pymodule]
fn _rust_lib(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    // Initialize logging for debug builds
    #[cfg(debug_assertions)]
    {
        env_logger::init_from_env(env_logger::Env::new().default_filter_or("debug"));
    }

    // Register validation functions with panic safety
    m.add_function(wrap_pyfunction!(validate_buffer_size_py, m)?)?;
    m.add_function(wrap_pyfunction!(validate_utf8_string_py, m)?)?;
    m.add_function(wrap_pyfunction!(validate_u8_range_py, m)?)?;

    // Register routing class
    m.add_class::<PyRouteMatcher>()?;

    // Register all submodules with error handling
    catch_panic(|| request::register_module(m))?;
    catch_panic(|| dependencies::register_module(m))?;
    catch_panic(|| response::register_module(m))?;
    catch_panic(|| validation::register_module(m))?;

    // Add version info
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;

    // Add object counter for debugging
    #[cfg(debug_assertions)]
    {
        m.add("_object_counter", OBJECT_COUNTER.load(Ordering::SeqCst))?;
    }

    Ok(())
}
