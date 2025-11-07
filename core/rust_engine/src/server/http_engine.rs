use http_body_util::{BodyExt, Full};
use hyper::header::{CONTENT_TYPE, HeaderName, HeaderValue};
use hyper::service::service_fn;
use hyper::{HeaderMap, Method, Request, Response, body::Bytes, body::Incoming};
use hyper_util::rt::{TokioExecutor, TokioIo};
use hyper_util::server::conn::auto::Builder;
use hyper_util::server::graceful::GracefulShutdown;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyTuple};
use serde_json::json;
use std::collections::HashMap;
use std::net::SocketAddr;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use tokio::net::TcpListener;
use tokio::runtime::Runtime;
use tokio::sync::oneshot;
use tokio::task::JoinSet;

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
        Python::with_gil(|py| Self {
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
    // Connection limits and timeouts
    connection_limit: usize,
    connection_timeout_secs: u64,
    request_timeout_secs: u64,
    read_timeout_secs: u64,
    write_timeout_secs: u64,
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
            connection_limit: 100,          // Default: 100 concurrent connections
            connection_timeout_secs: 60,    // Default: 60s connection timeout 
            request_timeout_secs: 30,       // Default: 30s request timeout
            read_timeout_secs: 10,          // Default: 10s read timeout
            write_timeout_secs: 10,         // Default: 10s write timeout
        }
    }
    
    /// Set the maximum number of concurrent connections.
    #[pyo3(text_signature = "(self, limit)")]
    fn set_connection_limit(&mut self, limit: usize) {
        self.connection_limit = limit;
    }
    
    /// Get the current connection limit.
    #[pyo3(text_signature = "(self)")]
    fn get_connection_limit(&self) -> usize {
        self.connection_limit
    }
    
    /// Set the connection timeout in seconds.
    #[pyo3(text_signature = "(self, timeout_secs)")]
    fn set_connection_timeout(&mut self, timeout_secs: u64) {
        self.connection_timeout_secs = timeout_secs;
    }
    
    /// Set the request timeout in seconds.
    #[pyo3(text_signature = "(self, timeout_secs)")]
    fn set_request_timeout(&mut self, timeout_secs: u64) {
        self.request_timeout_secs = timeout_secs;
    }
    
    /// Set the read timeout in seconds.
    #[pyo3(text_signature = "(self, timeout_secs)")]
    fn set_read_timeout(&mut self, timeout_secs: u64) {
        self.read_timeout_secs = timeout_secs;
    }
    
    /// Set the write timeout in seconds.
    #[pyo3(text_signature = "(self, timeout_secs)")]
    fn set_write_timeout(&mut self, timeout_secs: u64) {
        self.write_timeout_secs = timeout_secs;
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
            if self.handle.is_some() {
                return Err(pyo3::exceptions::PyRuntimeError::new_err(
                    "server already running",
                ));
            }
            let addr: SocketAddr = addr
                .parse::<SocketAddr>()
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
            
            // Clone configuration for the server thread
            let routes = self.routes.clone();
            let keep_alive = self.keep_alive;
            let connection_limit = self.connection_limit;
            let connection_timeout = self.connection_timeout_secs;
            let request_timeout = self.request_timeout_secs;
            let read_timeout = self.read_timeout_secs;
            let write_timeout = self.write_timeout_secs;
            
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
                    let graceful = GracefulShutdown::new();
                    let mut join_set: JoinSet<()> = JoinSet::new();
                    let mut shutdown_requested = false;

                    // Connection counter and limiter
                    let active_connections = Arc::new(std::sync::atomic::AtomicUsize::new(0));
                    let connection_limiter = Arc::new(tokio::sync::Semaphore::new(connection_limit));
                    
                    loop {
                        if shutdown_requested {
                            break;
                        }
                        tokio::select! {
                            _ = &mut rx => {
                                shutdown_requested = true;
                            }
                            accept = listener.accept(), if !shutdown_requested => {
                                let (stream, client_addr) = match accept {
                                    Ok(s) => s,
                                    Err(e) => {
                                        eprintln!("accept error: {e}");
                                        continue;
                                    }
                                };
                                
                                // Try to acquire a permit, or reject the connection if at limit
                                let permit = match connection_limiter.clone().try_acquire_owned() {
                                    Ok(permit) => permit,
                                    Err(_) => {
                                        eprintln!("Connection limit reached, rejecting connection from {}", client_addr);
                                        continue;
                                    }
                                };
                                
                                let active_connections = active_connections.clone();
                                let count = active_connections.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                                eprintln!("Connection accepted from {}, active: {}/{}", client_addr, count, connection_limit);
                                
                                // Set socket-level timeouts
                                if let Err(e) = stream.set_nodelay(true) {
                                    eprintln!("Could not set TCP_NODELAY: {}", e);
                                }
                                
                                // Configure connection options
                                let routes = routes.clone();
                                let mut http_builder = builder.clone();
                                
                                // Set keep-alive if configured
                                if let Some(keep_alive_secs) = keep_alive {
                                    http_builder.http1().keep_alive(true).keep_alive_timeout(std::time::Duration::from_secs(keep_alive_secs));
                                } else {
                                    http_builder.http1().keep_alive(false);
                                }
                                
                                // Set connection timeout
                                http_builder.http1().timer(tokio::time::sleep(std::time::Duration::from_secs(connection_timeout)));
                                
                                let watcher = graceful.watcher();
                                let active_conn_clone = active_connections.clone();
                                
                                join_set.spawn(async move {
                                    // Use drop guard to ensure we decrement counter and release permit
                                    struct ConnectionCleanup {
                                        counter: Arc<std::sync::atomic::AtomicUsize>,
                                        _permit: tokio::sync::OwnedSemaphorePermit,
                                        addr: SocketAddr,
                                    }
                                    
                                    impl Drop for ConnectionCleanup {
                                        fn drop(&mut self) {
                                            let count = self.counter.fetch_sub(1, std::sync::atomic::Ordering::SeqCst) - 1;
                                            eprintln!("Connection from {} closed, active: {}", self.addr, count);
                                        }
                                    }
                                    
                                    let _cleanup = ConnectionCleanup {
                                        counter: active_conn_clone,
                                        _permit: permit,
                                        addr: client_addr,
                                    };
                                    
                                    // Apply request timeout
                                    let io = TokioIo::new(stream);
                                    
                                    // Use a timeout wrapper for the service
                                    let service = service_fn(move |req| {
                                        let routes = routes.clone();
                                        async move {
                                            match tokio::time::timeout(
                                                std::time::Duration::from_secs(request_timeout), 
                                                handle_request(req, routes)
                                            ).await {
                                                Ok(result) => result,
                                                Err(_) => {
                                                    eprintln!("Request timeout after {} seconds", request_timeout);
                                                    let response = json_response(
                                                        408, 
                                                        serde_json::json!({"detail": "Request timeout"})
                                                    );
                                                    Ok(response)
                                                }
                                            }
                                        }
                                    });
                                    
                                    let connection = http_builder.serve_connection(io, service).into_owned();
                                    if let Err(err) = watcher.watch(connection).await {
                                        eprintln!("server error: {err}");
                                    }
                                });
                            }
                            Some(res) = join_set.join_next(), if !join_set.is_empty() => {
                                if let Err(join_err) = res {
                                    if join_err.is_panic() {
                                        eprintln!("connection task panicked: {join_err}");
                                    } else {
                                        eprintln!("connection task error: {join_err}");
                                    }
                                }
                            }
                        }
                    }

                    drop(listener);
                    graceful.shutdown().await;
                    while let Some(res) = join_set.join_next().await {
                        if let Err(join_err) = res {
                            if join_err.is_panic() {
                                eprintln!("connection task panicked: {join_err}");
                            } else {
                                eprintln!("connection task error: {join_err}");
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
    fn shutdown(&mut self, py: Python<'_>) {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(());
        }
        if let Some(handle) = self.handle.take() {
            py.allow_threads(move || {
                let _ = handle.join();
            });
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
    let (parts, body_stream) = req.into_parts();
    let method = parts.method.clone();
    let path = parts.uri.path().to_string();
    let query = parts.uri.query().unwrap_or("").to_string();
    let headers = parts.headers.clone();
    let mut body = Some(body_stream);
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
                return Ok(json_response(
                    500,
                    json!({
                        "detail": "Internal Server Error"
                    }),
                ));
            }
        }
    };
    if let Some(routes_for_method) = routes_vec {
        for route in routes_for_method.iter() {
            match match_route(&route.pattern, &path_segments) {
                Match::Ok(params) => {
                    let body_bytes = match body.take() {
                        Some(stream) => stream.collect().await?.to_bytes(),
                        None => Bytes::new(),
                    };
                    let response = call_handler(
                        &route.handler,
                        &route.pattern,
                        params,
                        body_bytes,
                        &query,
                        &headers,
                    )
                    .await;
                    return Ok(response);
                }
                Match::ValidationError(errors) => {
                    let detail: Vec<_> = errors
                        .into_iter()
                        .map(|err| {
                            json!({
                                "loc": err.loc,
                                "msg": err.msg,
                                "type": err.typ,
                            })
                        })
                        .collect();
                    return Ok(json_response(422, json!({ "detail": detail })));
                }
                Match::Miss => {}
            }
        }
    }

    // fallback health, readiness, and liveness endpoints
    if method == Method::GET && matches!(path.as_str(), "/health" | "/ready" | "/live") {
        return Ok(Response::builder()
            .header("content-type", "application/json")
            .body(Full::from("{\"status\":\"ok\"}"))
            .unwrap());
    }

    Ok(json_response(404, json!({ "detail": "not found" })))
}

/// Result of attempting to match a path to a route pattern.
#[derive(Debug)]
enum Match {
    Ok(Vec<String>),
    ValidationError(Vec<PathValidationError>),
    Miss,
}

#[derive(Debug, Clone)]
struct PathValidationError {
    loc: Vec<String>,
    msg: &'static str,
    typ: &'static str,
}

/// Parse a path template into segments.
fn parse_pattern(path: &str) -> PyResult<Vec<Segment>> {
    let mut segments = Vec::new();
    for seg in path.trim_matches('/').split('/') {
        if seg.is_empty() {
            continue;
        }
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
    let mut errors: Vec<PathValidationError> = Vec::new();
    for (seg, part) in pattern.iter().zip(path.iter()) {
        match seg {
            Segment::Static(s) => {
                if s != part {
                    return Match::Miss;
                }
            }
            Segment::Param { name, ty } => match ty {
                ParamType::Int => {
                    if part.parse::<i64>().is_err() {
                        errors.push(PathValidationError {
                            loc: vec!["path".to_string(), name.clone()],
                            msg: "value is not a valid integer",
                            typ: "type_error.integer",
                        });
                    } else {
                        params.push(part.to_string());
                    }
                }
                ParamType::Str => params.push(part.to_string()),
            },
        }
    }
    if errors.is_empty() {
        Match::Ok(params)
    } else {
        Match::ValidationError(errors)
    }
}

fn json_response(status: u16, body: serde_json::Value) -> Response<Full<Bytes>> {
    const FALLBACK: &[u8] = b"{\"detail\":\"Internal Server Error\"}";
    let encoded = serde_json::to_vec(&body).unwrap_or_else(|_| FALLBACK.to_vec());
    Response::builder()
        .status(status)
        .header(CONTENT_TYPE, HeaderValue::from_static("application/json"))
        .body(Full::from(encoded))
        .unwrap_or_else(|_| {
            Response::builder()
                .status(500)
                .header(CONTENT_TYPE, HeaderValue::from_static("application/json"))
                .body(Full::from(FALLBACK.to_vec()))
                .expect("fallback response")
        })
}

/// Call a Python handler with body and extracted parameters.
async fn call_handler(
    handler: &Py<PyAny>,
    pattern: &[Segment],
    params: Vec<String>,
    body: Bytes,
    query: &str,
    headers: &HeaderMap,
) -> Response<Full<Bytes>> {
    let result = catch_unwind(AssertUnwindSafe(|| {
        Python::with_gil(|py| -> PyResult<Py<PyAny>> {
            let py_body = PyBytes::new(py, body.as_ref());
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
            let py_headers = PyDict::new(py);
            for (name, value) in headers.iter() {
                if let Ok(val_str) = value.to_str() {
                    py_headers.set_item(name.as_str(), val_str)?;
                }
            }
            handler.call1(py, (py_body, params_tuple, py_query, py_headers))
        })
    }));
    match result {
        Ok(Ok(obj)) => match extract_response(obj) {
            Ok((status, body_bytes, headers_map)) => {
                let mut builder = Response::builder().status(status);
                let mut has_content_type = false;
                for (key, value) in headers_map {
                    if let (Ok(name), Ok(val)) = (
                        HeaderName::from_bytes(key.as_bytes()),
                        HeaderValue::from_str(&value),
                    ) {
                        if name == CONTENT_TYPE {
                            has_content_type = true;
                        }
                        builder = builder.header(name, val);
                    }
                }
                if !has_content_type {
                    builder =
                        builder.header(CONTENT_TYPE, HeaderValue::from_static("application/json"));
                }
                builder.body(Full::from(body_bytes)).unwrap()
            }
            Err(e) => {
                eprintln!("handler error: {e}");
                json_response(500, json!({ "detail": "Internal Server Error" }))
            }
        },
        Ok(Err(e)) => {
            eprintln!("handler error: {e}");
            json_response(500, json!({ "detail": "Internal Server Error" }))
        }
        Err(_) => {
            eprintln!("handler panic");
            json_response(500, json!({ "detail": "Internal Server Error" }))
        }
    }
}

/// Extract response components from the Python return value.
fn extract_response(obj: Py<PyAny>) -> PyResult<(u16, Vec<u8>, HashMap<String, String>)> {
    Python::with_gil(|py| {
        let bound = obj.bind(py);
        let tuple = bound.downcast::<PyTuple>().map_err(|_| {
            pyo3::exceptions::PyTypeError::new_err("expected (status, body, headers) tuple")
        })?;
        if tuple.len() != 3 {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "expected (status, body, headers) tuple",
            ));
        }
        let status: u16 = tuple.get_item(0)?.extract()?;
        let body_item = tuple.get_item(1)?;
        let body_bytes = if let Ok(text) = body_item.extract::<String>() {
            text.into_bytes()
        } else if let Ok(chunks) = body_item.extract::<Vec<String>>() {
            chunks.join("").into_bytes()
        } else if let Ok(raw) = body_item.extract::<Vec<u8>>() {
            raw
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "response body must be str, bytes, or list[str]",
            ));
        };
        let headers = tuple.get_item(2)?.extract()?;
        Ok((status, body_bytes, headers))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_pattern_static_and_params() {
        let pattern = parse_pattern("/users/{id:int}/items/{name}").unwrap();
        assert!(matches!(pattern[0], Segment::Static(ref s) if s == "users"));
        assert!(matches!(pattern[1], Segment::Param { .. }));
        assert!(matches!(pattern[2], Segment::Static(ref s) if s == "items"));
        assert!(matches!(pattern[3], Segment::Param { .. }));
    }

    #[test]
    fn match_route_success_and_params() {
        let pattern = parse_pattern("/users/{id:int}/items/{name}").unwrap();
        let path = ["users", "42", "items", "hat"];
        match match_route(&pattern, &path) {
            Match::Ok(params) => assert_eq!(params, vec!["42".to_string(), "hat".to_string()]),
            other => panic!("expected Match::Ok, got {:?}", other),
        }
    }

    #[test]
    fn match_route_validation_error_on_type_mismatch() {
        let pattern = parse_pattern("/users/{id:int}").unwrap();
        let path = ["users", "not-int"];
        match match_route(&pattern, &path) {
            Match::ValidationError(errors) => {
                assert_eq!(errors.len(), 1);
                let err = &errors[0];
                assert_eq!(err.loc, vec!["path".to_string(), "id".to_string()]);
                assert_eq!(err.msg, "value is not a valid integer");
                assert_eq!(err.typ, "type_error.integer");
            }
            other => panic!("expected Match::ValidationError, got {:?}", other),
        }
    }
}