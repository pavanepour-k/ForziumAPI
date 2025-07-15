use crate::errors::ProjectError;
use crate::routing::types::{HttpMethod, Route};
use regex::Regex;

pub fn parse_route_pattern(
    pattern: &str,
    method: &str,
    handler_id: &str,
) -> Result<Route, ProjectError> {
    let mut regex_pattern = String::from("^");
    let mut param_names = Vec::new();

    let parts: Vec<&str> = pattern.split('/').collect();
    for part in parts {
        if part.starts_with('{') && part.ends_with('}') {
            let param_name = &part[1..part.len() - 1];
            param_names.push(param_name.to_string());
            regex_pattern.push_str(r"([^/]+)");
        } else if !part.is_empty() {
            regex_pattern.push('/');
            regex_pattern.push_str(&regex::escape(part));
        }
    }
    regex_pattern.push('$');

    let path_regex = Regex::new(&regex_pattern).map_err(|e| ProjectError::Validation {
        code: "RUST_CORE_VALIDATION_INVALID_ROUTE_PATTERN".to_string(),
        message: format!("Invalid route pattern: {}", e),
    })?;

    Ok(Route {
        path: pattern.to_string(),
        method: parse_http_method(method)?,
        handler_id: handler_id.to_string(),
        path_regex,
        param_names,
    })
}

fn parse_http_method(method: &str) -> Result<HttpMethod, ProjectError> {
    match method.to_uppercase().as_str() {
        "GET" => Ok(HttpMethod::GET),
        "POST" => Ok(HttpMethod::POST),
        "PUT" => Ok(HttpMethod::PUT),
        "DELETE" => Ok(HttpMethod::DELETE),
        "PATCH" => Ok(HttpMethod::PATCH),
        "HEAD" => Ok(HttpMethod::HEAD),
        "OPTIONS" => Ok(HttpMethod::OPTIONS),
        "TRACE" => Ok(HttpMethod::TRACE),
        _ => Err(ProjectError::Validation {
            code: "RUST_CORE_VALIDATION_INVALID_HTTP_METHOD".to_string(),
            message: format!("Invalid HTTP method: {}", method),
        }),
    }
}
