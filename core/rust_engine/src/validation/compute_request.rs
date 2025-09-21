use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Schema validator for ComputeRequest.
#[pyclass]
pub struct ComputeRequestSchema;

#[pymethods]
impl ComputeRequestSchema {
    #[new]
    fn new() -> Self {
        Self
    }

    /// Validate input data and return a dict on success.
    fn validate<'py>(
        &self,
        py: Python<'py>,
        input: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let mapping: HashMap<String, Py<PyAny>> = input.extract()?;

        let data_obj = mapping
            .get("data")
            .ok_or_else(|| PyValueError::new_err("data field required"))?;
        let data: Vec<Vec<f64>> = data_obj.extract(py)?;
        if data.is_empty() || data.iter().any(|r| r.len() != data[0].len()) {
            return Err(PyValueError::new_err(
                "Data must be a non-empty rectangular matrix",
            ));
        }

        let operation_obj = mapping
            .get("operation")
            .ok_or_else(|| PyValueError::new_err("operation field required"))?;
        let operation: String = operation_obj.extract(py)?;

        // Parameters optional dict
        let params = match mapping.get("parameters") {
            Some(obj) => obj.extract::<HashMap<String, Py<PyAny>>>(py)?,
            None => HashMap::new(),
        };

        let out = PyDict::new(py);
        out.set_item("data", data)?;
        out.set_item("operation", operation)?;
        out.set_item("parameters", params)?;
        Ok(out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::Python;

    #[test]
    fn valid_request() {
        Python::with_gil(|py| {
            let schema = ComputeRequestSchema::new();
            let data = PyDict::new(py);
            data.set_item("data", vec![vec![1.0, 2.0], vec![3.0, 4.0]])
                .unwrap();
            data.set_item("operation", "add").unwrap();
            let out = schema.validate(py, &data).unwrap();
            let op_any = out.get_item("operation").unwrap().unwrap();
            let op: String = op_any.extract().unwrap();
            assert_eq!(op, "add");
        });
    }

    #[test]
    fn invalid_matrix() {
        Python::with_gil(|py| {
            let schema = ComputeRequestSchema::new();
            let data = PyDict::new(py);
            data.set_item("data", vec![vec![1.0], vec![2.0, 3.0]])
                .unwrap();
            data.set_item("operation", "add").unwrap();
            assert!(schema.validate(py, &data).is_err());
        });
    }

    #[test]
    fn missing_operation() {
        Python::with_gil(|py| {
            let schema = ComputeRequestSchema::new();
            let data = PyDict::new(py);
            data.set_item("data", vec![vec![1.0, 2.0]]).unwrap();
            assert!(schema.validate(py, &data).is_err());
        });
    }

    #[test]
    fn invalid_parameters_type() {
        Python::with_gil(|py| {
            let schema = ComputeRequestSchema::new();
            let data = PyDict::new(py);
            data.set_item("data", vec![vec![1.0, 2.0]]).unwrap();
            data.set_item("operation", "add").unwrap();
            data.set_item("parameters", 42).unwrap();
            assert!(schema.validate(py, &data).is_err());
        });
    }
}
