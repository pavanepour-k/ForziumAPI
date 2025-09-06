//! Machine learning inference utilities.

use crate::error::ForziumError;
use pyo3::prelude::*;
use pyo3::types::PyType;
use std::fs;

/// Simple linear model with weights and bias.
#[derive(Debug)]
pub struct LinearModel {
    weights: Vec<f64>,
    bias: f64,
}

impl LinearModel {
    /// Load model parameters from a text file.
    ///
    /// The file must contain whitespace-separated numbers with the
    /// first value as the bias followed by weights.
    pub fn load(path: &str) -> Result<Self, ForziumError> {
        let content = fs::read_to_string(path)
            .map_err(|_| ForziumError::Compute("model file not found".into()))?;
        let nums: Vec<f64> = content
            .split_whitespace()
            .map(|s| s.parse::<f64>())
            .collect::<Result<_, _>>()
            .map_err(|_| ForziumError::Compute("invalid model data".into()))?;
        if nums.len() < 2 {
            return Err(ForziumError::Compute("model data incomplete".into()));
        }
        let bias = nums[0];
        let weights = nums[1..].to_vec();
        Ok(Self { weights, bias })
    }

    /// Predict output for the given input vector.
    pub fn predict(&self, input: &[f64]) -> Result<f64, ForziumError> {
        if input.len() != self.weights.len() {
            return Err(ForziumError::Compute("input length mismatch".into()));
        }
        let mut sum = self.bias;
        for (w, x) in self.weights.iter().zip(input.iter()) {
            sum += w * x;
        }
        Ok(sum)
    }
}

#[pyclass(name = "LinearModel")]
pub struct PyLinearModel {
    inner: LinearModel,
}

#[pymethods]
impl PyLinearModel {
    /// Load a model from disk.
    #[classmethod]
    pub fn load(_cls: &Bound<PyType>, path: &str) -> PyResult<Self> {
        let inner = LinearModel::load(path).map_err(PyErr::from)?;
        Ok(Self { inner })
    }

    /// Predict output for the given input vector.
    pub fn predict(&self, input: Vec<f64>) -> PyResult<f64> {
        self.inner.predict(&input).map_err(Into::into)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_file_path() -> String {
        let mut path = std::env::temp_dir();
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        path.push(format!("model_{nanos}.txt"));
        path.to_string_lossy().into_owned()
    }

    #[test]
    fn load_and_predict_ok() {
        let path = temp_file_path();
        fs::write(&path, "1 2 3").unwrap();
        let model = LinearModel::load(&path).unwrap();
        assert_eq!(model.predict(&[4.0, 5.0]).unwrap(), 24.0);
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn load_missing_file() {
        let err = LinearModel::load("/no/such/model").unwrap_err();
        matches!(err, ForziumError::Compute(_));
    }

    #[test]
    fn predict_shape_mismatch() {
        let path = temp_file_path();
        fs::write(&path, "0 1 2").unwrap();
        let model = LinearModel::load(&path).unwrap();
        let err = model.predict(&[1.0]).unwrap_err();
        matches!(err, ForziumError::Compute(_));
        fs::remove_file(path).unwrap();
    }
}
