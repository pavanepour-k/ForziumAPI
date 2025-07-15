use forzium::routing::{parse_route_pattern, HttpMethod, RouteMatcher};
use pyo3::prelude::*;
use std::collections::HashMap;

#[pyclass]
pub struct PyRouteMatcher {
    matcher: RouteMatcher,
}

#[pymethods]
impl PyRouteMatcher {
    #[new]
    fn new() -> Self {
        Self {
            matcher: RouteMatcher::new(),
        }
    }

    fn add_route(&mut self, pattern: &str, method: &str, handler_id: &str) -> PyResult<()> {
        let route = parse_route_pattern(pattern, method, handler_id)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        self.matcher.add_route(route);
        Ok(())
    }

    fn match_path(&self, path: &str, method: &str) -> PyResult<(String, HashMap<String, String>)> {
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
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Invalid HTTP method",
                ))
            }
        };

        let route_match = self
            .matcher
            .match_route(path, &http_method)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

        Ok((route_match.handler_id, route_match.path_params))
    }
}
