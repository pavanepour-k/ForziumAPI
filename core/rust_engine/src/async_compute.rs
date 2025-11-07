use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::thread;
use tokio::sync::oneshot;
use std::sync::{Arc, Mutex};
use crate::compute::tensor_ops;
use crate::error::ForziumError;

/// AsyncCompute provides methods to execute computations asynchronously 
/// without blocking the Python GIL
#[pyclass]
pub struct AsyncCompute {
    runtime: Arc<Mutex<tokio::runtime::Runtime>>,
}

#[pymethods]
impl AsyncCompute {
    #[new]
    fn new() -> Self {
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(4)
            .thread_name("forzium-async-worker")
            .enable_all()
            .build()
            .unwrap();
        
        Self {
            runtime: Arc::new(Mutex::new(runtime)),
        }
    }
    
    /// Execute a matrix multiplication asynchronously and return a handle
    fn matmul<'py>(
        &self,
        py: Python<'py>,
        a: Vec<Vec<f64>>,
        b: Vec<Vec<f64>>,
    ) -> PyResult<ComputeHandle> {
        // Create channel for returning result
        let (tx, rx) = oneshot::channel();
        
        // Clone the data to move into the new thread
        let a_clone = a.clone();
        let b_clone = b.clone();
        
        // Start the computation in a separate thread to release GIL
        py.allow_threads(|| {
            let runtime = self.runtime.lock().unwrap();
            runtime.spawn(async move {
                let result = tensor_ops::matmul(&a_clone, &b_clone);
                let _ = tx.send(result);
            });
        });
        
        Ok(ComputeHandle { receiver: rx })
    }
    
    /// Execute a convolution asynchronously and return a handle
    fn conv2d<'py>(
        &self,
        py: Python<'py>,
        input: Vec<Vec<f64>>,
        kernel: Vec<Vec<f64>>,
    ) -> PyResult<ComputeHandle> {
        // Create channel for returning result
        let (tx, rx) = oneshot::channel();
        
        // Clone the data to move into the new thread
        let input_clone = input.clone();
        let kernel_clone = kernel.clone();
        
        // Start the computation in a separate thread to release GIL
        py.allow_threads(|| {
            let runtime = self.runtime.lock().unwrap();
            runtime.spawn(async move {
                let result = tensor_ops::conv2d(&input_clone, &kernel_clone);
                let _ = tx.send(result);
            });
        });
        
        Ok(ComputeHandle { receiver: rx })
    }
    
    /// Execute a simd matrix multiplication asynchronously and return a handle
    fn simd_matmul<'py>(
        &self,
        py: Python<'py>,
        a: Vec<Vec<f64>>,
        b: Vec<Vec<f64>>,
    ) -> PyResult<ComputeHandle> {
        // Create channel for returning result
        let (tx, rx) = oneshot::channel();
        
        // Clone the data to move into the new thread
        let a_clone = a.clone();
        let b_clone = b.clone();
        
        // Start the computation in a separate thread to release GIL
        py.allow_threads(|| {
            let runtime = self.runtime.lock().unwrap();
            runtime.spawn(async move {
                let result = tensor_ops::simd_matmul(&a_clone, &b_clone);
                let _ = tx.send(result);
            });
        });
        
        Ok(ComputeHandle { receiver: rx })
    }
}

/// Handle for an asynchronous computation
/// Allows checking if result is ready and retrieving it
#[pyclass]
pub struct ComputeHandle {
    receiver: oneshot::Receiver<Result<Vec<Vec<f64>>, ForziumError>>,
}

#[pymethods]
impl ComputeHandle {
    /// Check if the result is ready without blocking
    fn is_ready(&self, py: Python<'_>) -> PyResult<bool> {
        py.allow_threads(|| {
            // Poll the receiver without waiting
            let mut receiver = &self.receiver;
            match &mut receiver {
                ref mut rx if rx.is_closed() => Ok(true),
                _ => Ok(false),
            }
        })
    }
    
    /// Wait for the result and return it
    /// This will block until the result is ready
    fn get_result(&mut self, py: Python<'_>) -> PyResult<Vec<Vec<f64>>> {
        py.allow_threads(|| {
            // Take the receiver
            let rx = std::mem::replace(&mut self.receiver, oneshot::channel().1);
            
            // Wait for the result
            match rx.blocking_recv() {
                Ok(Ok(result)) => Ok(result),
                Ok(Err(err)) => Err(err.into()),
                Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
                    "Computation task failed unexpectedly",
                )),
            }
        })
    }
    
    /// Try to get the result without blocking
    /// Returns None if the result is not ready
    fn try_get_result(&mut self, py: Python<'_>) -> PyResult<Option<Vec<Vec<f64>>>> {
        if !self.is_ready(py)? {
            return Ok(None);
        }
        
        let result = self.get_result(py)?;
        Ok(Some(result))
    }
}

/// Add a helper function to create a task queue
#[pyfunction]
pub fn create_async_compute() -> AsyncCompute {
    AsyncCompute::new()
}
