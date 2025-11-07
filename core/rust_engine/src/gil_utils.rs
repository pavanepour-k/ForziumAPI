use pyo3::prelude::*;
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use tokio::sync::{mpsc, oneshot};

/// Result type for GIL-free operations.
type ComputeResult<T> = Result<T, String>;

/// Worker channel message type.
enum WorkerMsg<T, R> {
    Task {
        task: T,
        result_tx: oneshot::Sender<ComputeResult<R>>,
    },
    Terminate,
}

/// A worker that performs compute operations without holding the GIL.
/// This allows Python threads to run concurrently with compute-intensive Rust operations.
pub struct GilFreeWorker<T, R, F>
where
    T: Send + 'static,
    R: Send + 'static,
    F: Fn(T) -> ComputeResult<R> + Send + 'static,
{
    task_tx: mpsc::Sender<WorkerMsg<T, R>>,
    _join_handle: Arc<thread::JoinHandle<()>>,
}

impl<T, R, F> GilFreeWorker<T, R, F>
where
    T: Send + 'static,
    R: Send + 'static,
    F: Fn(T) -> ComputeResult<R> + Send + 'static,
{
    /// Create a new worker that will execute tasks in a separate thread without holding the GIL.
    pub fn new(processor: F) -> Self {
        let (task_tx, mut task_rx) = mpsc::channel::<WorkerMsg<T, R>>(16);
        
        let join_handle = thread::spawn(move || {
            while let Some(msg) = task_rx.blocking_recv() {
                match msg {
                    WorkerMsg::Task { task, result_tx } => {
                        let result = processor(task);
                        let _ = result_tx.send(result);
                    }
                    WorkerMsg::Terminate => break,
                }
            }
        });
        
        Self {
            task_tx,
            _join_handle: Arc::new(join_handle),
        }
    }
    
    /// Submit a task to be executed without holding the GIL.
    pub async fn submit(&self, task: T) -> ComputeResult<R> {
        let (result_tx, result_rx) = oneshot::channel();
        
        if self.task_tx.send(WorkerMsg::Task { task, result_tx }).await.is_err() {
            return Err("Worker thread has terminated".into());
        }
        
        result_rx.await.unwrap_or_else(|_| Err("Worker thread died".into()))
    }
}

impl<T, R, F> Drop for GilFreeWorker<T, R, F>
where
    T: Send + 'static,
    R: Send + 'static,
    F: Fn(T) -> ComputeResult<R> + Send + 'static,
{
    fn drop(&mut self) {
        let _ = self.task_tx.try_send(WorkerMsg::Terminate);
    }
}

/// Executes a compute-intensive function without holding the GIL, allowing Python threads to run.
/// This is useful for long-running operations that don't need to interact with Python objects.
pub async fn compute_without_gil<F, R>(py: Python<'_>, func: F) -> PyResult<R>
where
    F: FnOnce() -> Result<R, String> + Send + 'static,
    R: Send + 'static,
{
    // Create a oneshot channel for the result
    let (tx, rx) = oneshot::channel();
    
    // Release the GIL and run the compute function in a separate thread
    py.allow_threads(|| {
        thread::spawn(move || {
            let result = func();
            let _ = tx.send(result);
        });
    });
    
    // Wait for the result with a timeout
    match tokio::time::timeout(Duration::from_secs(300), rx).await {
        Ok(Ok(Ok(result))) => Ok(result),
        Ok(Ok(Err(err))) => Err(pyo3::exceptions::PyRuntimeError::new_err(err)),
        Ok(Err(_)) => Err(pyo3::exceptions::PyRuntimeError::new_err("Worker thread died")),
        Err(_) => Err(pyo3::exceptions::PyTimeoutError::new_err("Operation timed out after 300 seconds")),
    }
}

/// A PyO3 function wrapper that releases the GIL during computation
#[macro_export]
macro_rules! release_gil {
    ($py:expr, $body:expr) => {
        $py.allow_threads(|| $body)
    };
}
