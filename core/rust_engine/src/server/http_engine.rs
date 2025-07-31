use hyper::service::{make_service_fn, service_fn};
use hyper::{Body, Method, Request, Response, Server};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyTuple};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use tokio::runtime::Runtime;
use tokio::sync::oneshot;

/// Minimal ASGI-compatible HTTP server written in Rust.
/// Currently handles only a basic `/health` endpoint.
#[pyclass]
pub struct ForziumHttpServer {
    shutdown_tx: Option<oneshot::Sender<()>>,
    handle: Option<JoinHandle<()>>,
    handlers: Arc<Mutex<HashMap<(Method, String), Py<PyAny>>>>,
}

#[pymethods]
impl ForziumHttpServer {
    #[new]
    fn new() -> Self {
        Self {
            shutdown_tx: None,
            handle: None,
            handlers: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Register a Python handler for a method and path.
    fn add_route(&mut self, method: &str, path: &str, handler: Py<PyAny>) -> PyResult<()> {
        let method = method
            .parse::<Method>()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        self.handlers
            .lock()
            .expect("lock")
            .insert((method, path.to_string()), handler);
        Ok(())
    }

    /// Start serving on the given address, e.g. "127.0.0.1:8080".
    #[pyo3(text_signature = "(self, addr)")]
    fn serve(&mut self, addr: &str) -> PyResult<()> {
        let addr: SocketAddr = addr
            .parse::<SocketAddr>()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let handlers = self.handlers.clone();
        let (tx, rx) = oneshot::channel();
        let thread = std::thread::spawn(move || {
            let rt = Runtime::new().expect("runtime");
            rt.block_on(async move {
                let make_svc = make_service_fn(move |_conn| {
                    let handlers = handlers.clone();
                    async move {
                        Ok::<_, hyper::Error>(service_fn(move |req| {
                            handle_request(req, handlers.clone())
                        }))
                    }
                });
                let server = Server::bind(&addr).serve(make_svc);
                let graceful = server.with_graceful_shutdown(async {
                    let _ = rx.await;
                });
                if let Err(err) = graceful.await {
                    eprintln!("server error: {err}");
                }
            });
        });
        self.shutdown_tx = Some(tx);
        self.handle = Some(thread);
        Ok(())
    }

    /// Stop the server and wait for the background thread to finish.
    fn shutdown(&mut self) {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(());
        }
        if let Some(handle) = self.handle.take() {
            let _ = handle.join();
        }
    }
}

async fn handle_request(
    req: Request<Body>,
    handlers: Arc<Mutex<HashMap<(Method, String), Py<PyAny>>>>,
) -> Result<Response<Body>, hyper::Error> {
    let key = (req.method().clone(), req.uri().path().to_string());
    let handler_opt = {
        handlers
            .lock()
            .expect("lock")
            .get(&key)
            .map(|h| Python::with_gil(|py| h.clone_ref(py)))
    };
    if let Some(handler) = handler_opt {
        let body_bytes = hyper::body::to_bytes(req.into_body()).await?;
        let py_obj = Python::with_gil(|py| -> PyResult<PyObject> {
            let arg = PyBytes::new(py, &body_bytes);
            let h = handler.clone_ref(py);
            h.call1(py, (arg,))
        });
        let response = match py_obj {
            Ok(obj) => Python::with_gil(|py| -> PyResult<Response<Body>> {
                let (status, body): (u16, String) = obj.extract(py)?;
                Ok(Response::builder()
                    .status(status)
                    .header("content-type", "application/json")
                    .body(Body::from(body))
                    .unwrap())
            })
            .unwrap_or_else(|e| {
                eprintln!("handler error: {e}");
                Response::builder()
                    .status(500)
                    .body(Body::from("{\"detail\":\"server error\"}"))
                    .unwrap()
            }),
            Err(e) => {
                eprintln!("handler error: {e}");
                Response::builder()
                    .status(500)
                    .body(Body::from("{\"detail\":\"server error\"}"))
                    .unwrap()
            }
        };
        Ok(response)
    } else if key.0 == Method::GET && key.1 == "/health" {
        let body = Body::from("{\"status\":\"ok\"}");
        Ok(Response::new(body))
    } else {
        Ok(Response::builder().status(404).body(Body::empty()).unwrap())
    }
}
