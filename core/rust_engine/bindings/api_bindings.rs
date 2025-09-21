use pyo3::prelude::*;

use crate::bindings::{error_handlers::map_error, type_converters::py_list_to_vec_i64};
use crate::error::{ForziumError, catch_unwind_py};

/// Sum a list of integers passed from Python.
#[pyfunction]
pub fn sum_list(values: &Bound<PyAny>) -> PyResult<i64> {
    catch_unwind_py(|| {
        let vec = py_list_to_vec_i64(values)?;
        if vec.is_empty() {
            return Err(map_error(ForziumError::Validation("empty list".into())));
        }
        Ok(vec.iter().sum())
    })
}

/// Echo the provided sequence back to Python.
#[pyfunction]
pub fn echo_list(values: &Bound<PyAny>) -> PyResult<Vec<i64>> {
    catch_unwind_py(|| py_list_to_vec_i64(values))
}

/// Return the active span identifier from Python telemetry.
#[pyfunction]
pub fn current_span_id(py: Python<'_>) -> PyResult<Option<String>> {
    let mon = PyModule::import(py, "infrastructure.monitoring")?;
    mon.getattr("get_current_span_id")?.call0()?.extract()
}

/// Register API bindings on the supplied module.
pub fn register(m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_list, m)?)?;
    m.add_function(wrap_pyfunction!(echo_list, m)?)?;
    m.add_function(wrap_pyfunction!(current_span_id, m)?)?;
    Ok(())
}
