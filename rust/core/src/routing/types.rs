use crate::errors::ProjectError;
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum HttpMethod {
    GET,
    POST,
    PUT,
    DELETE,
    PATCH,
    HEAD,
    OPTIONS,
    TRACE,
}

#[derive(Debug, Clone)]
pub struct Route {
    pub path: String,
    pub method: HttpMethod,
    pub handler_id: String,
    pub path_regex: regex::Regex,
    pub param_names: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct RouteMatch {
    pub handler_id: String,
    pub path_params: HashMap<String, String>,
}
