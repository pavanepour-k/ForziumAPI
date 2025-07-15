use crate::errors::ProjectError;
use crate::routing::types::{HttpMethod, Route, RouteMatch};
use std::collections::HashMap;

pub struct RouteMatcher {
    routes: Vec<Route>,
}

impl RouteMatcher {
    pub fn new() -> Self {
        Self { routes: Vec::new() }
    }

    pub fn add_route(&mut self, route: Route) {
        self.routes.push(route);
    }

    pub fn match_route(&self, path: &str, method: &HttpMethod) -> Result<RouteMatch, ProjectError> {
        for route in &self.routes {
            if route.method != *method {
                continue;
            }

            if let Some(captures) = route.path_regex.captures(path) {
                let mut path_params = HashMap::new();
                for (i, param_name) in route.param_names.iter().enumerate() {
                    if let Some(value) = captures.get(i + 1) {
                        path_params.insert(param_name.clone(), value.as_str().to_string());
                    }
                }

                return Ok(RouteMatch {
                    handler_id: route.handler_id.clone(),
                    path_params,
                });
            }
        }

        Err(ProjectError::Validation {
            code: "RUST_CORE_VALIDATION_ROUTE_NOT_FOUND".to_string(),
            message: format!("No route found for {:?} {}", method, path),
        })
    }
}

impl Default for RouteMatcher {
    fn default() -> Self {
        Self::new()
    }
}
