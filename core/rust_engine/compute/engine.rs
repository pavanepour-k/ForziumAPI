use std::collections::HashMap;

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::compute::tensor_ops;
use crate::error::ForziumError;

/// Function pointer signature for registered operations.
type OperationFn = fn(Vec<Vec<f64>>, &Bound<PyDict>) -> Result<Vec<Vec<f64>>, ForziumError>;

/// Simple compute engine mapping operation names to functions.
#[pyclass]
pub struct ComputeEngine {
    registry: HashMap<&'static str, OperationFn>,
}

impl Default for ComputeEngine {
    fn default() -> Self {
        let mut registry: HashMap<&'static str, OperationFn> = HashMap::new();
        registry.insert("multiply", op_multiply as OperationFn);
        registry.insert("add", op_add as OperationFn);
        registry.insert("matmul", op_matmul as OperationFn);
        Self { registry }
    }
}

#[pymethods]
impl ComputeEngine {
    #[new]
    pub fn new() -> Self {
        Self::default()
    }

    /// Return whether the engine supports the given operation.
    pub fn supports(&self, operation: &str) -> bool {
        self.registry.contains_key(operation)
    }

    /// Execute the specified operation with parameters.
    #[pyo3(signature = (data, operation, params, cancel=None))]
    pub fn compute(
        &self,
        _py: Python,
        data: Vec<Vec<f64>>,
        operation: &str,
        params: &Bound<PyDict>,
        cancel: Option<bool>,
    ) -> PyResult<Vec<Vec<f64>>> {
        if cancel.unwrap_or(false) {
            return Err(ForziumError::Cancelled("operation cancelled".into()).into());
        }
        match self.registry.get(operation) {
            Some(func) => func(data, params).map_err(Into::into),
            None => Err(ForziumError::Compute("unsupported operation".into()).into()),
        }
    }
}

fn op_multiply(data: Vec<Vec<f64>>, params: &Bound<PyDict>) -> Result<Vec<Vec<f64>>, ForziumError> {
    let factor = match params
        .get_item("factor")
        .map_err(|_| ForziumError::Validation("factor invalid".into()))?
    {
        Some(v) => v
            .extract::<f64>()
            .map_err(|_| ForziumError::Validation("factor invalid".into()))?,
        None => 1.0,
    };
    tensor_ops::multiply(&data, factor)
}

fn op_add(data: Vec<Vec<f64>>, params: &Bound<PyDict>) -> Result<Vec<Vec<f64>>, ForziumError> {
    let addend = match params
        .get_item("addend")
        .map_err(|_| ForziumError::Validation("addend invalid".into()))?
    {
        Some(v) => v
            .extract::<f64>()
            .map_err(|_| ForziumError::Validation("addend invalid".into()))?,
        None => 0.0,
    };
    tensor_ops::add(&data, addend)
}

fn op_matmul(data: Vec<Vec<f64>>, params: &Bound<PyDict>) -> Result<Vec<Vec<f64>>, ForziumError> {
    let other = match params
        .get_item("matrix_b")
        .map_err(|_| ForziumError::Validation("matrix_b invalid".into()))?
    {
        Some(v) => v
            .extract::<Vec<Vec<f64>>>()
            .map_err(|_| ForziumError::Validation("matrix_b invalid".into()))?,
        None => return Err(ForziumError::Validation("matrix_b missing".into())),
    };
    tensor_ops::matmul(&data, &other)
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::types::PyDict;
    use pyo3::Python;

    #[test]
    fn multiply_works() {
        Python::with_gil(|py| {
            let engine = ComputeEngine::new();
            let params = PyDict::new_bound(py);
            params.set_item("factor", 2.0).unwrap();
            let result = engine
                .compute(py, vec![vec![1.0, 2.0]], "multiply", &params)
                .unwrap();
            assert_eq!(result, vec![vec![2.0, 4.0]]);
        });
    }

    #[test]
    fn unsupported_op_errors() {
        Python::with_gil(|py| {
            let engine = ComputeEngine::new();
            let params = PyDict::new_bound(py);
            let err = engine
                .compute(py, vec![vec![1.0]], "nope", &params)
                .unwrap_err();
            assert!(err.is_instance_of::<pyo3::exceptions::PyRuntimeError>(py));
        });
    }
}
