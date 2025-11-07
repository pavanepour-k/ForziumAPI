//! Unit tests for the FFI boundary between Rust and Python.
//!
//! These tests focus on the Rust side of the FFI boundary.
//! They verify the correct handling of Python objects, error propagation,
//! and memory management across the boundary.

#[cfg(test)]
mod tests {
    use super::super::*;
    use pyo3::prelude::*;
    use pyo3::types::{PyDict, PyList};
    use std::sync::{Arc, Mutex};
    use std::thread;

    // Test helper to convert a Rust matrix to a Python list of lists
    fn matrix_to_py(py: Python<'_>, matrix: &[Vec<f64>]) -> PyResult<Py<PyAny>> {
        let list = PyList::empty(py);
        for row in matrix {
            let py_row = PyList::empty(py);
            for &val in row {
                py_row.append(val)?;
            }
            list.append(py_row)?;
        }
        Ok(list.into())
    }

    #[test]
    fn test_matrix_conversion() {
        // Test that matrices are correctly converted between Rust and Python
        Python::with_gil(|py| {
            // Create a Rust matrix
            let matrix = vec![vec![1.0, 2.0], vec![3.0, 4.0]];

            // Convert to Python
            let py_matrix = matrix_to_py(py, &matrix).unwrap();

            // Create a Python function that returns the matrix
            let locals = PyDict::new(py);
            locals.set_item("matrix", py_matrix).unwrap();
            let code = "def identity(x): return x\nresult = identity(matrix)";
            py.run(code, None, Some(locals)).unwrap();

            // Get the result back
            let result = locals.get_item("result").unwrap();

            // Convert back to Rust
            let rust_result: Vec<Vec<f64>> = result.extract(py).unwrap();

            // Verify it's the same
            assert_eq!(rust_result, matrix);
        });
    }

    #[test]
    fn test_error_propagation() {
        // Test that Rust errors are correctly propagated to Python
        Python::with_gil(|py| {
            // Create a function that panics
            let err_func = py_fn!(py, || -> PyResult<()> {
                Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "Test error",
                ))
            });

            // Call the function from Python
            let locals = PyDict::new(py);
            locals.set_item("err_func", err_func).unwrap();
            let code = "try:\n    err_func()\n    success = False\nexcept RuntimeError:\n    success = True";
            py.run(code, None, Some(locals)).unwrap();

            // Check that the error was caught
            let success = locals
                .get_item("success")
                .unwrap()
                .extract::<bool>(py)
                .unwrap();
            assert!(success);
        });
    }

    #[test]
    fn test_gil_release() {
        // Test that compute-intensive operations release the GIL
        Python::with_gil(|py| {
            // Create a Python function that does something with the GIL released
            let gil_release_func = py_fn!(py, || -> PyResult<()> {
                py.allow_threads(|| {
                    // Simulate work
                    std::thread::sleep(std::time::Duration::from_millis(100));
                });
                Ok(())
            });

            // Create a counter to check parallel execution
            let counter = Arc::new(Mutex::new(0));
            let counter_clone = counter.clone();

            // Call the function from Python and check if we can run code in parallel
            let locals = PyDict::new(py);
            locals
                .set_item("gil_release_func", gil_release_func)
                .unwrap();

            // Start a thread that counts while the GIL is released
            let handle = thread::spawn(move || {
                let mut count = 0;
                let start = std::time::Instant::now();
                while start.elapsed() < std::time::Duration::from_millis(200) {
                    count += 1;
                }
                *counter_clone.lock().unwrap() = count;
            });

            // Run the GIL-releasing function
            let code = "gil_release_func()";
            py.run(code, None, Some(locals)).unwrap();

            // Wait for the counting thread
            handle.join().unwrap();

            // Check that the counter advanced, indicating parallel execution
            let count = *counter.lock().unwrap();
            assert!(count > 0, "Counter should have advanced during GIL release");
        });
    }

    #[test]
    fn test_thread_safety() {
        // Test thread-safe access to Python from multiple Rust threads
        Python::with_gil(|py| {
            // Create a thread-safe Python object container
            let locals = PyDict::new(py);
            locals.set_item("value", 0i32).unwrap();

            // Shared Python code to run in each thread
            let code = "
def increment():
    global value
    value += 1
    return value
";
            py.run(code, None, Some(locals)).unwrap();

            // Get the Python increment function
            let increment = locals.get_item("increment").unwrap();
            let safe_increment = increment.to_object(py);

            // Create threads that call the Python function
            let mut handles = vec![];
            let num_threads = 5;

            for _ in 0..num_threads {
                let inc_func = safe_increment.clone();
                let handle = thread::spawn(move || {
                    // Each thread will acquire the GIL and call the Python function
                    Python::with_gil(|py| {
                        let _ = inc_func.call0(py).unwrap();
                    });
                });
                handles.push(handle);
            }

            // Wait for all threads
            for handle in handles {
                handle.join().unwrap();
            }

            // Check that the value was incremented correctly
            let final_value = locals
                .get_item("value")
                .unwrap()
                .extract::<i32>(py)
                .unwrap();
            assert_eq!(final_value, num_threads);
        });
    }

    #[test]
    fn test_memory_management() {
        // Test memory management for objects crossing the FFI boundary
        Python::with_gil(|py| {
            // Create a Python object and a Rust reference to it
            let obj = PyDict::new(py);
            obj.set_item("key", "value").unwrap();
            let obj_ref = obj.to_object(py);

            // Drop the original reference
            drop(obj);

            // The object should still be valid through obj_ref
            let recovered = obj_ref.cast_as::<PyDict>(py).unwrap();
            let value = recovered
                .get_item("key")
                .unwrap()
                .extract::<String>(py)
                .unwrap();
            assert_eq!(value, "value");

            // Now create a reference cycle and test gc behavior
            let locals = PyDict::new(py);
            let code = "
import gc

# Create reference cycle
a = {}
b = {}
a['ref'] = b
b['ref'] = a

# Store the id of one object
import sys
id_a = id(a)

# Remove references
del a
del b

# Force collection
gc.collect()

# Check if objects were collected (returns None if collected)
collected = sys.getrefcount(id_a) if id_a in globals() else None
";
            py.run(code, None, Some(locals)).unwrap();

            // Check that the objects were collected
            let collected = locals.get_item("collected").unwrap();
            assert!(collected.is_none(py));
        });
    }

    #[test]
    fn test_exception_handling() {
        // Test handling of Python exceptions in Rust
        Python::with_gil(|py| {
            // Create a Python function that raises different exceptions
            let code = "
def raise_value_error():
    raise ValueError('Invalid value')

def raise_runtime_error():
    raise RuntimeError('Runtime failure')
";
            py.run(code, None, None).unwrap();

            // Get the functions
            let value_error_fn = py.eval("raise_value_error", None, None).unwrap();
            let runtime_error_fn = py.eval("raise_runtime_error", None, None).unwrap();

            // Call and catch the ValueError
            let result = value_error_fn.call0(py);
            assert!(result.is_err());
            let err = result.unwrap_err();
            assert!(err.is_instance_of::<pyo3::exceptions::PyValueError>(py));

            // Call and catch the RuntimeError
            let result = runtime_error_fn.call0(py);
            assert!(result.is_err());
            let err = result.unwrap_err();
            assert!(err.is_instance_of::<pyo3::exceptions::PyRuntimeError>(py));

            // Convert Python exceptions to Rust errors
            let result = value_error_fn
                .call0(py)
                .map_err(|e| format!("Python error: {}", e));
            assert!(result.is_err());
            let err_string = result.unwrap_err();
            assert!(err_string.contains("Invalid value"));
        });
    }
}
