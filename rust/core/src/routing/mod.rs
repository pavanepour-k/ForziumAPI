pub struct Route {
    pub path: String,
    pub method: HttpMethod,
    pub handler_id: String,
}

pub fn parse_path_template(template: &str) -> Result<PathPattern, ProjectError> {
    // Implementation for {param} style path parsing
}

// rust/core/src/validation/pydantic.rs
pub fn validate_model_fields(data: &[u8], schema: &Schema) -> Result<ValidatedData, ProjectError> {
    // Fast validation logic
}
