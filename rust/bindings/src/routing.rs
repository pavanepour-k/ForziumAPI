use forzium::routing::{parse_route_pattern, HttpMethod, RouteMatcher};
use pyo3::prelude::*;
use std::collections::HashMap;
use std::panic;
use std::sync::atomic::{AtomicU64, Ordering};

// Object counter for tracking
static ROUTE_MATCHER_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Catch panics for routing operations
fn catch_panic_routing<F, R>(f: F) -> PyResult<R>
where
    F: FnOnce() -> PyResult<R> + panic::UnwindSafe,
{
    match panic::catch_unwind(f) {
        Ok(result) => result,
        Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
            "Rust panic occurred in routing module",
        )),
    }
}

#[pyclass]
pub struct PyRouteMatcher {
    matcher: RouteMatcher,
    #[pyo3(get)]
    id: u64, // Unique ID for lifetime tracking
}

#[pymethods]
impl PyRouteMatcher {
    #[new]
    fn new() -> Self {
        let id = ROUTE_MATCHER_COUNTER.fetch_add(1, Ordering::SeqCst);

        #[cfg(debug_assertions)]
        log::debug!("Creating PyRouteMatcher {}", id);

        Self {
            matcher: RouteMatcher::new(),
            id,
        }
    }

    fn add_route(&mut self, pattern: &str, method: &str, handler_id: &str) -> PyResult<()> {
        catch_panic_routing(|| {
            // Validate inputs
            if pattern.is_empty() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Route pattern cannot be empty",
                ));
            }

            if pattern.len() > 2048 {
                // Max path length
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Route pattern exceeds maximum length (2048)",
                ));
            }

            if handler_id.is_empty() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Handler ID cannot be empty",
                ));
            }

            #[cfg(debug_assertions)]
            log::debug!(
                "PyRouteMatcher {}: Adding route {} {} -> {}",
                self.id,
                method,
                pattern,
                handler_id
            );

            let route = parse_route_pattern(pattern, method, handler_id)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

            self.matcher.add_route(route);
            Ok(())
        })
    }

    fn match_path(&self, path: &str, method: &str) -> PyResult<(String, HashMap<String, String>)> {
        catch_panic_routing(|| {
            // Validate inputs
            if path.is_empty() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Path cannot be empty",
                ));
            }

            if path.len() > 2048 {
                // Max path length
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Path exceeds maximum length (2048)",
                ));
            }

            #[cfg(debug_assertions)]
            log::debug!(
                "PyRouteMatcher {}: Matching path {} {}",
                self.id,
                method,
                path
            );

            let http_method = match method.to_uppercase().as_str() {
                "GET" => HttpMethod::GET,
                "POST" => HttpMethod::POST,
                "PUT" => HttpMethod::PUT,
                "DELETE" => HttpMethod::DELETE,
                "PATCH" => HttpMethod::PATCH,
                "HEAD" => HttpMethod::HEAD,
                "OPTIONS" => HttpMethod::OPTIONS,
                "TRACE" => HttpMethod::TRACE,
                _ => {
                    return Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Invalid HTTP method: {}",
                        method
                    )))
                }
            };

            let route_match = self
                .matcher
                .match_route(path, &http_method)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

            Ok((route_match.handler_id, route_match.path_params))
        })
    }

    /// Get the number of registered routes
    fn route_count(&self) -> usize {
        self.matcher.routes.len()
    }

    /// Clear all routes
    fn clear(&mut self) {
        #[cfg(debug_assertions)]
        log::debug!("PyRouteMatcher {}: Clearing all routes", self.id);

        self.matcher = RouteMatcher::new();
    }

    /// String representation for debugging
    fn __repr__(&self) -> String {
        format!(
            "PyRouteMatcher(id={}, routes={})",
            self.id,
            self.route_count()
        )
    }
}

/// Implement Drop to track object lifecycle
impl Drop for PyRouteMatcher {
    fn drop(&mut self) {
        #[cfg(debug_assertions)]
        log::debug!(
            "Dropping PyRouteMatcher {} with {} routes",
            self.id,
            self.route_count()
        );

        // Clean up any resources if needed
        // Currently RouteMatcher doesn't hold external resources,
        // but this ensures proper cleanup if that changes
    }
}
