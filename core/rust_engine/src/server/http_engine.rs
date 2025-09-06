use http_body_util::{BodyExt, Full};
use hyper::service::service_fn;
use hyper::{body::Bytes, body::Incoming, Method, Request, Response};
use hyper_util::rt::{TokioExecutor, TokioIo};
use hyper_util::server::conn::auto::Builder;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyTuple};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use tokio::net::TcpListener;
use tokio::runtime::Runtime;
use tokio::sync::oneshot;

use crate::error::catch_unwind_py;

/// Route segment representation.
#[derive(Clone)]
enum Segment {
    Static(String),
    Param {
        #[allow(dead_code)]
        name: String,
        ty: ParamType,
    },
}

/// Supported parameter types for path segments.
#[derive(Clone, Copy)]
enum ParamType {
    Int,
    Str,
}

/// Stored route with parsed pattern and handler.
struct Route {
    pattern: Vec<Segment>,
    handler: Py<PyAny>,
}

impl Clone for Route {
    fn clone(&self) -> Self {
        Python::attach(|py| Self {
            pattern: self.pattern.clone(),
            handler: self.handler.clone_ref(py),
        })
    }
}

/// Minimal ASGI-compatible HTTP server written in Rust.
/// Currently handles only a basic `/health` endpoint.
// This attribute ensures the Python object is not `Send` across threads.
#[pyclass(unsendable)]
pub struct ForziumHttpServer {
    shutdown_tx: Option<oneshot::Sender<()>>,
    handle: Option<JoinHandle<()>>,
    routes: Arc<Mutex<HashMap<Method, Vec<Route>>>>,
    keep_alive: Option<u64>,
}

#[pymethods]
impl ForziumHttpServer {
    #[new]
    fn new() -> Self {
        Self {
            shutdown_tx: None,
            handle: None,
            routes: Arc::new(Mutex::new(HashMap::new())),
            keep_alive: None,
        }
    }

    /// Register a Python handler for a method and path.
    fn add_route(&mut self, method: &str, path: &str, handler: Py<PyAny>) -> PyResult<()> {
        catch_unwind_py(|| {
            let method = method
                .parse::<Method>()
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
            let pattern = parse_pattern(path)?;
            let mut routes = self
                .routes
                .lock()
                .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("lock"))?;
            routes
                .entry(method)
                .or_insert_with(Vec::new)
                .push(Route { pattern, handler });
            Ok(())
        })
    }

    /// Start serving on the given address, e.g. "127.0.0.1:8080".
    #[pyo3(text_signature = "(self, addr)")]
    fn serve(&mut self, addr: &str) -> PyResult<()> {
        catch_unwind_py(|| {
            let addr: SocketAddr = addr
                .parse::<SocketAddr>()
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
            let routes = self.routes.clone();
            let keep_alive = self.keep_alive;
            let (tx, mut rx) = oneshot::channel();
            let thread = std::thread::spawn(move || {
                let rt = match Runtime::new() {
                    Ok(rt) => rt,
                    Err(e) => {
                        eprintln!("runtime error: {e}");
                        return;
                    }
                };
                rt.block_on(async move {
                    let listener = match TcpListener::bind(addr).await {
                        Ok(l) => l,
                        Err(e) => {
                            eprintln!("bind error: {e}");
                            return;
                        }
                    };
                    let builder = Builder::new(TokioExecutor::new());
                    loop {
                        tokio::select! {
                            _ = &mut rx => break,
                            accept = listener.accept() => {
                                let (stream, _) = match accept {
                                    Ok(s) => s,
                                    Err(e) => { eprintln!("accept error: {e}"); continue; }
                                };
                                let routes = routes.clone();
                                let mut http_builder = builder.clone();
                                if keep_alive.is_some() {
                                    http_builder.http1().keep_alive(true);
                                }
                                tokio::spawn(async move {
                                    let io = TokioIo::new(stream);
                                    let service = service_fn(move |req| handle_request(req, routes.clone()));
                                    if let Err(err) = http_builder.serve_connection(io, service).await {
                                        eprintln!("server error: {err}");
                                    }
                                });
                            }
                        }
                    }
                });
            });
            self.shutdown_tx = Some(tx);
            self.handle = Some(thread);
            Ok(())
        })
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

    /// Set keep-alive timeout in seconds.
    fn set_keep_alive_timeout(&mut self, secs: u64) {
        self.keep_alive = Some(secs);
    }

    /// Retrieve configured keep-alive timeout.
    fn get_keep_alive_timeout(&self) -> u64 {
        self.keep_alive.unwrap_or(0)
    }
}

async fn handle_request(
    req: Request<Incoming>,
    routes: Arc<Mutex<HashMap<Method, Vec<Route>>>>,
) -> Result<Response<Full<Bytes>>, hyper::Error> {
    let method = req.method().clone();
    let path = req.uri().path().to_string();
    let query = req.uri().query().unwrap_or("").to_string();
    let path_segments: Vec<&str> = path
        .trim_matches('/')
        .split('/')
        .filter(|s| !s.is_empty())
        .collect();

    // try matching registered routes
    let routes_vec = {
        match routes.lock() {
            Ok(guard) => guard.get(&method).cloned(),
            Err(_) => {
                return Ok(Response::builder()
                    .status(500)
                    .body(Full::from("{\"detail\":\"server error\"}"))
                    .unwrap());
            }
        }
    };
    if let Some(routes_for_method) = routes_vec {
        for route in routes_for_method.iter() {
            match match_route(&route.pattern, &path_segments) {
                Match::Ok(params) => {
                    let body_bytes = req.into_body().collect().await?.to_bytes();
                    let response =
                        call_handler(&route.handler, &route.pattern, params, body_bytes, &query)
                            .await;
                    return Ok(response);
                }
                Match::BadRequest => {
                    return Ok(Response::builder()
                        .status(400)
                        .body(Full::from("{\"detail\":\"bad request\"}"))
                        .unwrap());
                }
                Match::Miss => {}
            }
        }
    }

    // fallback health endpoint
    if method == Method::GET && path == "/health" {
        return Ok(Response::new(Full::from("{\"status\":\"ok\"}")));
    }

    Ok(Response::builder()
        .status(404)
        .body(Full::from("{\"detail\":\"not found\"}"))
        .unwrap())
}

/// Result of attempting to match a path to a route pattern.
enum Match {
    Ok(Vec<String>),
    BadRequest,
    Miss,
}

/// Parse a path template into segments.
fn parse_pattern(path: &str) -> PyResult<Vec<Segment>> {
    let mut segments = Vec::new();
    for seg in path.trim_matches('/').split('/') {
        if seg.starts_with('{') && seg.ends_with('}') {
            let inner = &seg[1..seg.len() - 1];
            let mut parts = inner.split(':');
            let name = parts
                .next()
                .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("bad segment"))?;
            let ty = match parts.next() {
                Some("int") => ParamType::Int,
                _ => ParamType::Str,
            };
            segments.push(Segment::Param {
                name: name.to_string(),
                ty,
            });
        } else {
            segments.push(Segment::Static(seg.to_string()));
        }
    }
    Ok(segments)
}

/// Attempt to match segments against a pattern, returning captured params.
fn match_route(pattern: &[Segment], path: &[&str]) -> Match {
    if pattern.len() != path.len() {
        return Match::Miss;
    }
    let mut params = Vec::new();
    for (seg, part) in pattern.iter().zip(path.iter()) {
        match seg {
            Segment::Static(s) => {
                if s != part {
                    return Match::Miss;
                }
            }
            Segment::Param { ty, .. } => match ty {
                ParamType::Int => {
                    if part.parse::<i64>().is_err() {
                        return Match::BadRequest;
                    }
                    params.push(part.to_string());
                }
                ParamType::Str => params.push(part.to_string()),
            },
        }
    }
    Match::Ok(params)
}

/// Call a Python handler with body and extracted parameters.
async fn call_handler(
    handler: &Py<PyAny>,
    pattern: &[Segment],
    params: Vec<String>,
    body: Bytes,
    query: &str,
) -> Response<Full<Bytes>> {
    let result = catch_unwind(AssertUnwindSafe(|| {
        Python::attach(|py| -> PyResult<Py<PyAny>> {
            let py_body = PyBytes::new(py, &body);
            let mut objs: Vec<Py<PyAny>> = Vec::new();
            for (seg, val) in pattern
                .iter()
                .filter_map(|s| match s {
                    Segment::Param { ty, .. } => Some(ty),
                    _ => None,
                })
                .zip(params.iter())
            {
                match seg {
                    ParamType::Int => {
                        let v: i64 = val.parse().unwrap_or_default();
                        objs.push(v.into_pyobject(py)?.unbind().into());
                    }
                    ParamType::Str => {
                        objs.push(val.clone().into_pyobject(py)?.unbind().into());
                    }
                }
            }
            let params_tuple = PyTuple::new(py, objs)?;
            let py_query = PyBytes::new(py, query.as_bytes());
            handler.call1(py, (py_body, params_tuple, py_query))
        })
    }));
    match result {
        Ok(Ok(obj)) => match extract_status_body(obj) {
            Ok((status, body)) => Response::builder()
                .status(status)
                .header("content-type", "application/json")
                .body(Full::from(body))
                .unwrap(),
            Err(e) => {
                eprintln!("handler error: {e}");
                Response::builder()
                    .status(500)
                    .body(Full::from("{\"detail\":\"server error\"}"))
                    .unwrap()
            }
        },
        Ok(Err(e)) => {
            eprintln!("handler error: {e}");
            Response::builder()
                .status(500)
                .body(Full::from("{\"detail\":\"server error\"}"))
                .unwrap()
        }
        Err(_) => {
            eprintln!("handler panic");
            Response::builder()
                .status(500)
                .body(Full::from("{\"detail\":\"server error\"}"))
                .unwrap()
        }
    }
}

/// Extract response status code and body from a Python object.
fn extract_status_body(obj: Py<PyAny>) -> PyResult<(u16, String)> {
    Python::attach(|py| obj.bind(py).extract())
}