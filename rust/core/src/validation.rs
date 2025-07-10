use crate::errors::ProjectError;

/// Buffer Size Validation (10MB limit)
pub fn validate_buffer_size(data: &[u8]) -> Result<(), ProjectError> {
    const MAX_SIZE: usize = 10_485_760;  // 10MB
    if data.len() > MAX_SIZE {
        Err(ProjectError::Validation {
            code: "RUST_CORE_VALIDATION_BUFFER_TOO_LARGE".to_string(),
            message: format!("Buffer size {} exceeds limit {}", data.len(), MAX_SIZE),
        })
    } else {
        Ok(())
    }
}

/// UTF-8 Validation
pub fn validate_utf8_string(data: &[u8]) -> Result<String, ProjectError> {
    std::str::from_utf8(data)
        .map(|s| s.to_string())
        .map_err(|e| ProjectError::Validation {
            code: "RUST_CORE_VALIDATION_INVALID_UTF8".to_string(),
            message: format!("Invalid UTF-8: {}", e),
        })
}

/// Num range Validation (0-255)
pub fn validate_u8_range(value: u8) -> Result<(), ProjectError> {
    if value < 0 || value > 255 {
        Err(ProjectError::Validation {
            code: "RUST_CORE_VALIDATION_OUT_OF_RANGE".to_string(),
            message: format!("Value {} out of range (0-255)", value),
        })
    } else {
        Ok(())
    }
}
