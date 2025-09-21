use pyo3::prelude::*;
use pyo3::types::{PyDict, PyModule};

#[path = "../bindings/mod.rs"]
mod bindings;
#[path = "../compute/mod.rs"]
pub mod compute;
pub mod error;
pub mod memory;
pub mod server;
pub mod validation;

use crate::compute::{
    data_transform, engine::ComputeEngine, ml_inference::PyLinearModel, rayon_metrics, tensor_ops,
};
use crate::error::ForziumError;
use crate::memory::gc_interface::force_gc;
use crate::server::http_engine::ForziumHttpServer;
use crate::validation::compute_request::ComputeRequestSchema;

#[pyfunction]
fn multiply(matrix: Vec<Vec<f64>>, factor: f64) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::multiply(&matrix, factor).map_err(Into::into)
}

#[pyfunction]
fn add(matrix: Vec<Vec<f64>>, addend: f64) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::add(&matrix, addend).map_err(Into::into)
}

#[pyfunction]
fn matmul(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::matmul(&a, &b).map_err(Into::into)
}

#[pyfunction]
fn simd_matmul(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::simd_matmul(&a, &b).map_err(Into::into)
}

#[pyfunction]
fn transpose(matrix: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::transpose(&matrix).map_err(Into::into)
}

#[pyfunction]
fn elementwise_add(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::elementwise_add(&a, &b).map_err(Into::into)
}

#[pyfunction]
fn simd_elementwise_add(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::simd_elementwise_add(&a, &b).map_err(Into::into)
}

#[pyfunction]
fn elementwise_mul(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::hadamard(&a, &b).map_err(Into::into)
}

#[pyfunction]
fn conv2d(a: Vec<Vec<f64>>, k: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::conv2d(&a, &k).map_err(Into::into)
}

#[pyfunction]
fn max_pool2d(a: Vec<Vec<f64>>, size: usize) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::max_pool2d(&a, size).map_err(Into::into)
}

#[pyfunction]
fn trigger_panic() -> PyResult<()> {
    Err(ForziumError::Compute("forced panic".into()).into())
}

#[pyfunction]
fn noop() -> PyResult<()> {
    Ok(())
}

#[pyfunction]
fn echo_u64(value: u64) -> PyResult<u64> {
    Ok(value)
}

#[pyfunction]
fn scale(vector: Vec<f64>, factor: f64) -> PyResult<Vec<f64>> {
    data_transform::scale(&vector, factor).map_err(Into::into)
}

#[pyfunction]
fn normalize(vector: Vec<f64>) -> PyResult<Vec<f64>> {
    data_transform::normalize(&vector).map_err(Into::into)
}

#[pyfunction]
fn reshape(vector: Vec<f64>, rows: usize, cols: usize) -> PyResult<Vec<Vec<f64>>> {
    data_transform::reshape(&vector, rows, cols).map_err(Into::into)
}

#[pyfunction]
fn rayon_pool_metrics(py: Python<'_>, reset: Option<bool>) -> PyResult<PyObject> {
    let snapshot = if reset.unwrap_or(false) {
        rayon_metrics::snapshot_and_reset()
            .map_err(|err| pyo3::exceptions::PyRuntimeError::new_err(err.to_string()))?
    } else {
        rayon_metrics::snapshot()
    };
    let dict = PyDict::new(py);
    dict.set_item("observed_threads", snapshot.observed_threads)?;
    dict.set_item("max_active_threads", snapshot.max_active_threads)?;
    dict.set_item("mean_active_threads", snapshot.mean_active_threads)?;
    dict.set_item("utilization_percent", snapshot.utilization_percent)?;
    dict.set_item("peak_saturation", snapshot.peak_saturation)?;
    dict.set_item("total_tasks_started", snapshot.total_tasks_started)?;
    dict.set_item("total_tasks_completed", snapshot.total_tasks_completed)?;
    dict.set_item("mean_task_duration_us", snapshot.mean_task_duration_us)?;
    dict.set_item("max_task_duration_us", snapshot.max_task_duration_us)?;
    dict.set_item("min_task_duration_us", snapshot.min_task_duration_us)?;
    dict.set_item("busy_time_seconds", snapshot.busy_time_seconds)?;
    dict.set_item("observation_seconds", snapshot.observation_seconds)?;
    Ok(dict.into())
}

#[pymodule]
fn forzium_engine(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(multiply, m)?)?;
    m.add_function(wrap_pyfunction!(add, m)?)?;
    m.add_function(wrap_pyfunction!(matmul, m)?)?;
    m.add_function(wrap_pyfunction!(simd_matmul, m)?)?;
    m.add_function(wrap_pyfunction!(transpose, m)?)?;
    m.add_function(wrap_pyfunction!(elementwise_add, m)?)?;
    m.add_function(wrap_pyfunction!(simd_elementwise_add, m)?)?;
    m.add_function(wrap_pyfunction!(elementwise_mul, m)?)?;
    m.add_function(wrap_pyfunction!(conv2d, m)?)?;
    m.add_function(wrap_pyfunction!(max_pool2d, m)?)?;
    m.add_function(wrap_pyfunction!(scale, m)?)?;
    m.add_function(wrap_pyfunction!(normalize, m)?)?;
    m.add_function(wrap_pyfunction!(reshape, m)?)?;
    m.add_function(wrap_pyfunction!(noop, m)?)?;
    m.add_function(wrap_pyfunction!(echo_u64, m)?)?;
    m.add_function(wrap_pyfunction!(force_gc, m)?)?;
    m.add_function(wrap_pyfunction!(rayon_pool_metrics, m)?)?;
    m.add_class::<PyLinearModel>()?;
    m.add_class::<ComputeEngine>()?;
    m.add_function(wrap_pyfunction!(trigger_panic, m)?)?;
    m.add_class::<ForziumHttpServer>()?;
    m.add_class::<ComputeRequestSchema>()?;
    m.add_class::<crate::memory::pool_allocator::PoolAllocator>()?;
    bindings::api_bindings::register(m)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::Python;

    #[test]
    fn trigger_panic_returns_error() {
        Python::with_gil(|py| {
            let err = trigger_panic().unwrap_err();
            assert!(err.is_instance_of::<pyo3::exceptions::PyRuntimeError>(py));
        });
    }

    #[test]
    fn noop_and_echo_functions_round_trip() {
        Python::with_gil(|_py| {
            noop().expect("noop should succeed");
            let value = echo_u64(42).expect("echo should return value");
            assert_eq!(value, 42);
            let zero = echo_u64(0).expect("echo should accept zero");
            assert_eq!(zero, 0);
        });
    }
}
