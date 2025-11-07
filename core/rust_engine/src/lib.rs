use pyo3::prelude::*;
use pyo3::types::{PyDict, PyModule};

pub mod async_compute;
#[path = "../bindings/mod.rs"]
mod bindings;
#[path = "../compute/mod.rs"]
pub mod compute;
pub mod error;
pub mod error_bridge;
pub mod gil_utils;
pub mod memory;
pub mod numpy_ops;
pub mod server;
pub mod validation;

use crate::async_compute::{create_async_compute, AsyncCompute, ComputeHandle};
use crate::compute::{
    data_transform,
    engine::ComputeEngine,
    ml_inference::PyLinearModel,
    rayon_metrics, simd_ops, tensor_ops,
    thread_pool::{
        configure_global_thread_pool, initialize_optimal_thread_pools, run_in_compute_pool,
        run_in_io_pool,
    },
};
use crate::error::ForziumError;
use crate::error_bridge::{
    get_last_error, set_capture_stack_traces, set_verbose_errors, ErrorCategory,
};
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
fn simd_matmul(py: Python<'_>, a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    let a_clone = a.clone();
    let b_clone = b.clone();

    // Release GIL during computation
    py.allow_threads(move || tensor_ops::simd_matmul(&a_clone, &b_clone).map_err(Into::into))
}

#[pyfunction]
fn transpose(matrix: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    tensor_ops::transpose(&matrix).map_err(Into::into)
}

#[pyfunction]
fn elementwise_add(py: Python<'_>, a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    let a_clone = a.clone();
    let b_clone = b.clone();

    // Release GIL during computation
    py.allow_threads(move || tensor_ops::elementwise_add(&a_clone, &b_clone).map_err(Into::into))
}

#[pyfunction]
fn simd_elementwise_add(
    py: Python<'_>,
    a: Vec<Vec<f64>>,
    b: Vec<Vec<f64>>,
) -> PyResult<Vec<Vec<f64>>> {
    let a_clone = a.clone();
    let b_clone = b.clone();

    // Release GIL during computation
    py.allow_threads(move || {
        tensor_ops::simd_elementwise_add(&a_clone, &b_clone).map_err(Into::into)
    })
}

#[pyfunction]
fn elementwise_mul(py: Python<'_>, a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    let a_clone = a.clone();
    let b_clone = b.clone();

    // Release GIL during computation
    py.allow_threads(move || tensor_ops::hadamard(&a_clone, &b_clone).map_err(Into::into))
}

#[pyfunction]
fn conv2d(py: Python<'_>, a: Vec<Vec<f64>>, k: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    let a_clone = a.clone();
    let k_clone = k.clone();

    // Release GIL during computation
    py.allow_threads(move || tensor_ops::conv2d(&a_clone, &k_clone).map_err(Into::into))
}

#[pyfunction]
fn max_pool2d(py: Python<'_>, a: Vec<Vec<f64>>, size: usize) -> PyResult<Vec<Vec<f64>>> {
    let a_clone = a.clone();
    let size_clone = size;

    // Release GIL during computation
    py.allow_threads(move || tensor_ops::max_pool2d(&a_clone, size_clone).map_err(Into::into))
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

/// Matrix multiplication using the best available SIMD instruction set
#[pyfunction]
fn optimal_matmul(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    simd_ops::optimal_matmul(&a, &b).map_err(Into::into)
}

/// Element-wise matrix addition using the best available SIMD instruction set
#[pyfunction]
fn optimal_add(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> PyResult<Vec<Vec<f64>>> {
    simd_ops::optimal_add(&a, &b).map_err(Into::into)
}

/// Returns the highest SIMD instruction set supported by the current CPU
#[pyfunction]
fn detect_simd_support() -> &'static str {
    simd_ops::detect_simd_support()
}

/// Run benchmark comparing basic operations with SIMD-optimized versions
#[pyfunction]
fn benchmark_simd() -> PyResult<String> {
    Ok(simd_ops::benchmark_simd_ops())
}

/// Initialize thread pools with optimal settings for the current hardware
#[pyfunction]
fn optimize_thread_pools() -> PyResult<()> {
    initialize_optimal_thread_pools().map_err(|err| pyo3::exceptions::PyRuntimeError::new_err(err))
}

/// Configure the global rayon thread pool with custom settings
#[pyfunction]
fn configure_rayon_thread_pool(
    thread_count: Option<usize>,
    stack_size_mb: Option<usize>,
    thread_lifetime_seconds: Option<u64>,
    breadth_first: Option<bool>,
) -> PyResult<()> {
    let threads = thread_count.unwrap_or_else(num_cpus::get);
    let stack = stack_size_mb.unwrap_or(2) * 1024 * 1024; // Convert MB to bytes
    let lifetime = thread_lifetime_seconds.unwrap_or(30) * 1000; // Convert seconds to ms
    let breadth = breadth_first.unwrap_or(false);

    configure_global_thread_pool(threads, stack, lifetime, breadth)
        .map_err(|err| pyo3::exceptions::PyRuntimeError::new_err(err))
}

/// Run a Python function in the optimized compute thread pool
#[pyfunction]
fn run_in_compute_threadpool(py: Python<'_>, func: &Bound<PyAny>) -> PyResult<PyObject> {
    // Create a oneshot channel for the result
    let (tx, rx) = std::sync::mpsc::channel();

    // Execute the function in the compute pool
    py.allow_threads(move || {
        run_in_compute_pool(|| {
            let result = Python::with_gil(|py| func.call0(py));
            tx.send(result).unwrap();
        });
    });

    // Receive the result
    match rx.recv() {
        Ok(result) => result,
        Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
            "Thread pool execution failed",
        )),
    }
}

/// Run a Python function in the optimized IO thread pool
#[pyfunction]
fn run_in_io_threadpool(py: Python<'_>, func: &Bound<PyAny>) -> PyResult<PyObject> {
    // Create a oneshot channel for the result
    let (tx, rx) = std::sync::mpsc::channel();

    // Execute the function in the IO pool
    py.allow_threads(move || {
        run_in_io_pool(|| {
            let result = Python::with_gil(|py| func.call0(py));
            tx.send(result).unwrap();
        });
    });

    // Receive the result
    match rx.recv() {
        Ok(result) => result,
        Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
            "Thread pool execution failed",
        )),
    }
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
    m.add_function(wrap_pyfunction!(optimal_matmul, m)?)?;
    m.add_function(wrap_pyfunction!(optimal_add, m)?)?;
    m.add_function(wrap_pyfunction!(detect_simd_support, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_simd, m)?)?;

    // Thread pool optimization functions
    m.add_function(wrap_pyfunction!(optimize_thread_pools, m)?)?;
    m.add_function(wrap_pyfunction!(configure_rayon_thread_pool, m)?)?;
    m.add_function(wrap_pyfunction!(run_in_compute_threadpool, m)?)?;
    m.add_function(wrap_pyfunction!(run_in_io_threadpool, m)?)?;
    m.add_class::<PyLinearModel>()?;
    m.add_class::<ComputeEngine>()?;
    m.add_function(wrap_pyfunction!(trigger_panic, m)?)?;
    m.add_class::<ForziumHttpServer>()?;
    m.add_class::<ComputeRequestSchema>()?;
    m.add_class::<crate::memory::pool_allocator::PoolAllocator>()?;
    m.add_class::<AsyncCompute>()?;
    m.add_class::<ComputeHandle>()?;
    m.add_function(wrap_pyfunction!(create_async_compute, m)?)?;
    m.add_class::<ErrorCategory>()?;
    m.add_function(wrap_pyfunction!(set_verbose_errors, m)?)?;
    m.add_function(wrap_pyfunction!(set_capture_stack_traces, m)?)?;
    m.add_function(wrap_pyfunction!(get_last_error, m)?)?;

    // Register submodules
    bindings::api_bindings::register(m)?;
    error_bridge::register(py, m)?;
    numpy_ops::register(py, m)?;
    Ok(())
}

#[cfg(test)]
mod ffi_tests;

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
