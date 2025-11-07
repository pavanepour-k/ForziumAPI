use numpy::ndarray::{Array1, Array2, ArrayView2};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use pyo3::PyObject;
use pyo3::Python;
use pyo3::{exceptions, PyResult};
use pyo3_numpy::{IntoPyArray, PyArray1, PyArray2, PyReadonlyArray2, PyReadwriteArray2};
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
    array: &PyArray2<f64>,
    factor: f64,
) -> PyResult<PyObject> {
    // Get a view of the array to ensure we don't copy the data
    let mut array_view = unsafe { array.as_array_mut() };

    // Apply the operation directly to the array's memory
    for elem in array_view.iter_mut() {
        *elem *= factor;
    }

    // Increment operation counter
    ZERO_COPY_OPS_COUNT.fetch_add(1, Ordering::Relaxed);

    // Return the modified array
    Ok(array.into_py(py))
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
    image: PyReadonlyArray2<f64>,
    kernel: PyReadonlyArray2<f64>,
) -> PyResult<PyObject> {
    // Get array views (zero-copy)
    let img_view = image.as_array();
    let kernel_view = kernel.as_array();

    // Extract dimensions
    let (img_rows, img_cols) = (img_view.shape()[0], img_view.shape()[1]);
    let (k_rows, k_cols) = (kernel_view.shape()[0], kernel_view.shape()[1]);

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
    let mut result = Array2::<f64>::zeros((out_rows, out_cols));

    // Calculate convolution using the array views (zero-copy)
    for i in 0..out_rows {
        for j in 0..out_cols {
            let mut sum = 0.0;
            for ki in 0..k_rows {
                for kj in 0..k_cols {
                    sum += img_view[[i + ki, j + kj]] * kernel_view[[ki, kj]];
                }
            }
            result[[i, j]] = sum;
        }
    }

    // Increment operation counter
    ZERO_COPY_OPS_COUNT.fetch_add(1, Ordering::Relaxed);

    // Convert result to Python/NumPy array
    Ok(result.into_pyarray(py).into_py(py))
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
    array_a: PyReadonlyArray2<f64>,
    array_b: PyReadonlyArray2<f64>,
    operation: &str,
) -> PyResult<PyObject> {
    // Get array views (zero-copy)
    let a_view = array_a.as_array();
    let b_view = array_b.as_array();

    // Check dimensions
    if a_view.shape() != b_view.shape() {
        return Err(exceptions::PyValueError::new_err(format!(
            "Arrays must have the same shape: {:?} vs {:?}",
            a_view.shape(),
            b_view.shape()
        )));
    }

    // Create output array
    let mut result = Array2::<f64>::zeros(a_view.raw_dim());

    // Apply operation
    match operation {
        "add" => {
            for ((i, j), val) in result.indexed_iter_mut() {
                *val = a_view[[i, j]] + b_view[[i, j]];
            }
        }
        "multiply" => {
            for ((i, j), val) in result.indexed_iter_mut() {
                *val = a_view[[i, j]] * b_view[[i, j]];
            }
        }
        "subtract" => {
            for ((i, j), val) in result.indexed_iter_mut() {
                *val = a_view[[i, j]] - b_view[[i, j]];
            }
        }
        "divide" => {
            for ((i, j), val) in result.indexed_iter_mut() {
                if b_view[[i, j]] == 0.0 {
                    return Err(exceptions::PyZeroDivisionError::new_err("Division by zero"));
                }
                *val = a_view[[i, j]] / b_view[[i, j]];
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

    // Convert result to Python/NumPy array
    Ok(result.into_pyarray(py).into_py(py))
}

/// Get the count of zero-copy operations performed
#[pyfunction]
pub fn get_zero_copy_ops_count() -> usize {
    ZERO_COPY_OPS_COUNT.load(Ordering::Relaxed)
}

/// Register the NumPy operations module functions
pub fn register(py: Python<'_>, parent_module: &PyModule) -> PyResult<()> {
    let m = PyModule::new(py, "numpy_ops")?;
    m.add_function(wrap_pyfunction!(zero_copy_multiply, m)?)?;
    m.add_function(wrap_pyfunction!(zero_copy_conv2d, m)?)?;
    m.add_function(wrap_pyfunction!(zero_copy_elementwise_op, m)?)?;
    m.add_function(wrap_pyfunction!(get_zero_copy_ops_count, m)?)?;
    parent_module.add_submodule(m)?;
    Ok(())
}
