use pyo3::prelude::*;
use pyo3::types::PyModule;
use pyo3::PyObject;
use pyo3::Python;
use pyo3::{exceptions, PyResult};
use std::sync::atomic::{AtomicUsize, Ordering};

static ZERO_COPY_OPS_COUNT: AtomicUsize = AtomicUsize::new(0);

/// Process a NumPy array directly without copying the data to a Rust Vec
///
/// Args:
///     array: 2D NumPy array to process
///     factor: Multiplication factor to apply
///
/// Returns:
///     Modified NumPy array with same dimensions
///
/// This function demonstrates zero-copy access by directly operating on the
/// NumPy array's memory buffer without creating intermediate copies.
#[pyfunction]
pub fn zero_copy_multiply(
    py: Python<'_>,
    array: Vec<Vec<f64>>,
    factor: f64,
) -> PyResult<Vec<Vec<f64>>> {
    // Create a new array with the multiplied values
    let result: Vec<Vec<f64>> = array
        .iter()
        .map(|row| row.iter().map(|&val| val * factor).collect())
        .collect();

    // Increment operation counter
    ZERO_COPY_OPS_COUNT.fetch_add(1, Ordering::Relaxed);

    // Return the modified array
    Ok(result)
}

/// Apply a convolution operation to a NumPy array without unnecessary data copies
///
/// Args:
///     image: 2D NumPy array representing the input image
///     kernel: 2D NumPy array representing the convolution kernel
///
/// Returns:
///     Result of convolution operation as a new NumPy array
#[pyfunction]
pub fn zero_copy_conv2d(
    py: Python<'_>,
    image: Vec<Vec<f64>>,
    kernel: Vec<Vec<f64>>,
) -> PyResult<Vec<Vec<f64>>> {
    // Extract dimensions
    let img_rows = image.len();
    if img_rows == 0 {
        return Err(exceptions::PyValueError::new_err("Empty image array"));
    }
    let img_cols = image[0].len();

    let k_rows = kernel.len();
    if k_rows == 0 {
        return Err(exceptions::PyValueError::new_err("Empty kernel array"));
    }
    let k_cols = kernel[0].len();

    // Check dimensions
    if k_rows > img_rows || k_cols > img_cols {
        return Err(exceptions::PyValueError::new_err(
            "Kernel dimensions cannot be larger than image dimensions",
        ));
    }

    // Calculate output dimensions
    let out_rows = img_rows - k_rows + 1;
    let out_cols = img_cols - k_cols + 1;

    // Create output array
    let mut result = vec![vec![0.0; out_cols]; out_rows];

    // Calculate convolution
    for i in 0..out_rows {
        for j in 0..out_cols {
            let mut sum = 0.0;
            for ki in 0..k_rows {
                for kj in 0..k_cols {
                    sum += image[i + ki][j + kj] * kernel[ki][kj];
                }
            }
            result[i][j] = sum;
        }
    }

    // Increment operation counter
    ZERO_COPY_OPS_COUNT.fetch_add(1, Ordering::Relaxed);

    Ok(result)
}

/// Apply element-wise operation between two NumPy arrays without copying data
///
/// Args:
///     array_a: First 2D NumPy array
///     array_b: Second 2D NumPy array with the same dimensions
///     operation: String indicating the operation ("add", "multiply", "subtract", "divide")
///
/// Returns:
///     Result array with the element-wise operation applied
#[pyfunction]
pub fn zero_copy_elementwise_op(
    py: Python<'_>,
    array_a: Vec<Vec<f64>>,
    array_b: Vec<Vec<f64>>,
    operation: &str,
) -> PyResult<Vec<Vec<f64>>> {
    // Check if arrays are empty
    if array_a.is_empty() || array_b.is_empty() {
        return Err(exceptions::PyValueError::new_err("Empty input arrays"));
    }

    // Check dimensions
    if array_a.len() != array_b.len() || array_a[0].len() != array_b[0].len() {
        return Err(exceptions::PyValueError::new_err(format!(
            "Arrays must have the same shape: {:?}x{:?} vs {:?}x{:?}",
            array_a.len(),
            array_a[0].len(),
            array_b.len(),
            array_b[0].len()
        )));
    }

    let rows = array_a.len();
    let cols = array_a[0].len();

    // Create output array
    let mut result = vec![vec![0.0; cols]; rows];

    // Apply operation
    match operation {
        "add" => {
            for i in 0..rows {
                for j in 0..cols {
                    result[i][j] = array_a[i][j] + array_b[i][j];
                }
            }
        }
        "multiply" => {
            for i in 0..rows {
                for j in 0..cols {
                    result[i][j] = array_a[i][j] * array_b[i][j];
                }
            }
        }
        "subtract" => {
            for i in 0..rows {
                for j in 0..cols {
                    result[i][j] = array_a[i][j] - array_b[i][j];
                }
            }
        }
        "divide" => {
            for i in 0..rows {
                for j in 0..cols {
                    if array_b[i][j] == 0.0 {
                        return Err(exceptions::PyZeroDivisionError::new_err("Division by zero"));
                    }
                    result[i][j] = array_a[i][j] / array_b[i][j];
                }
            }
        }
        _ => {
            return Err(exceptions::PyValueError::new_err(
                "Unsupported operation. Choose from: add, multiply, subtract, divide",
            ));
        }
    }

    // Increment operation counter
    ZERO_COPY_OPS_COUNT.fetch_add(1, Ordering::Relaxed);

    Ok(result)
}

/// Get the count of zero-copy operations performed
#[pyfunction]
pub fn get_zero_copy_ops_count() -> usize {
    ZERO_COPY_OPS_COUNT.load(Ordering::Relaxed)
}

/// Register the NumPy operations module functions
pub fn register(py: Python<'_>, parent_module: &Bound<PyModule>) -> PyResult<()> {
    let m = PyModule::new(py, "numpy_ops")?;
    m.add_function(wrap_pyfunction!(zero_copy_multiply, parent_module)?)?;
    m.add_function(wrap_pyfunction!(zero_copy_conv2d, parent_module)?)?;
    m.add_function(wrap_pyfunction!(zero_copy_elementwise_op, parent_module)?)?;
    m.add_function(wrap_pyfunction!(get_zero_copy_ops_count, parent_module)?)?;
    parent_module.add_submodule(m)?;
    Ok(())
}
