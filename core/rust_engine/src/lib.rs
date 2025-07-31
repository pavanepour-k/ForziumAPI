use pyo3::prelude::*;
use pyo3::types::PyModule;

pub mod memory;
pub mod server;
pub mod validation;

use crate::memory::gc_interface::force_gc;
use crate::server::http_engine::ForziumHttpServer;
use crate::validation::compute_request::ComputeRequestSchema;

#[pyfunction]
fn multiply(matrix: Vec<Vec<f64>>, factor: f64) -> Vec<Vec<f64>> {
    matrix
        .into_iter()
        .map(|row| row.into_iter().map(|x| x * factor).collect())
        .collect()
}

#[pyfunction]
fn add(matrix: Vec<Vec<f64>>, addend: f64) -> Vec<Vec<f64>> {
    matrix
        .into_iter()
        .map(|row| row.into_iter().map(|x| x + addend).collect())
        .collect()
}

#[pyfunction]
fn matmul(a: Vec<Vec<f64>>, b: Vec<Vec<f64>>) -> Vec<Vec<f64>> {
    let rows = a.len();
    let cols = b[0].len();
    let inner = b.len();
    let mut result = vec![vec![0.0; cols]; rows];
    for i in 0..rows {
        for k in 0..inner {
            for j in 0..cols {
                result[i][j] += a[i][k] * b[k][j];
            }
        }
    }
    result
}

#[pymodule]
fn forzium_engine(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(multiply, m)?)?;
    m.add_function(wrap_pyfunction!(add, m)?)?;
    m.add_function(wrap_pyfunction!(matmul, m)?)?;
    m.add_function(wrap_pyfunction!(force_gc, m)?)?;
    m.add_class::<ForziumHttpServer>()?;
    m.add_class::<ComputeRequestSchema>()?;
    Ok(())
}
