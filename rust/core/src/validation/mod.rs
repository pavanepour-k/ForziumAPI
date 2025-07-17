//! # FORZIUM VALIDATION MODULE
//!
//! **CORE VALIDATION SYSTEM WITH TRAIT-BASED ARCHITECTURE**
//!
//! This module provides the foundational `Validator` trait and concrete implementations
//! for high-performance input validation in the Forzium FastAPI replacement.
//!
//! ## VALIDATION PIPELINE
//!
//! 1. **BUFFER VALIDATION** - Size limits and memory safety
//! 2. **UTF-8 VALIDATION** - String encoding verification  
//! 3. **NUMERIC VALIDATION** - Range constraints and type safety
//! 4. **SCHEMA VALIDATION** - Structured data validation
//!
//! ## USAGE
//!
//! ```rust
//! use forzium::validation::{Validator, BufferValidator};
//!
//! let validator = BufferValidator::new(1024);
//! let result = validator.validate(b"test data".to_vec())?;
//! ```

#![allow(dead_code)] // Allow dead code for development phase
#![allow(unused_imports)] // Temporary allow for development

use crate::errors::ProjectError;
use serde_json::Value as JsonValue;
use std::collections::HashMap;

pub mod validators;

// Re-export concrete validators for public API
pub use validators::{
    BufferValidator, JsonType, NumericRangeValidator, SchemaValidator, Utf8Validator,
};

// **BACKWARD COMPATIBILITY LAYER**
// **MANDATE**: These functions MUST delegate to trait-based validators

/// **BUFFER SIZE VALIDATION** - Legacy compatibility function
pub fn validate_buffer_size(data: &[u8]) -> Result<(), ProjectError> {
    let validator = BufferValidator::default();
    validator.validate(data.to_vec())
}

/// **UTF-8 STRING VALIDATION** - Legacy compatibility function  
pub fn validate_utf8_string(data: &[u8]) -> Result<String, ProjectError> {
    let validator = Utf8Validator::new();
    validator.validate(data.to_vec())
}

/// **U8 RANGE VALIDATION** - Legacy compatibility function
pub fn validate_u8_range(value: u8) -> Result<(), ProjectError> {
    let validator = NumericRangeValidator::u8();
    validator.validate(value).map(|_| ())
}

/// **CORE VALIDATOR TRAIT**
///
/// **MANDATE**: ALL validation implementations MUST implement this trait.
/// **GUARANTEE**: Type-safe input/output with comprehensive error handling.
/// **PERFORMANCE**: Zero-allocation validation where possible.
pub trait Validator {
    /// **INPUT TYPE** - Data type accepted by this validator
    type Input;
    
    /// **OUTPUT TYPE** - Validated data type returned on success
    type Output;
    
    /// **VALIDATION EXECUTION**
    ///
    /// **PARAMETERS**:
    /// - `input: Self::Input` - Raw input data requiring validation
    ///
    /// **RETURNS**:
    /// - `Ok(Self::Output)` - Successfully validated data
    /// - `Err(ProjectError)` - Validation failure with structured error
    ///
    /// **GUARANTEE**: MUST NOT panic. ALL error conditions MUST return ProjectError.
    fn validate(&self, input: Self::Input) -> Result<Self::Output, ProjectError>;
}

/// **VALIDATION RESULT TYPE ALIASES**
pub type ValidationResult<T> = Result<T, ProjectError>;
pub type BufferResult = ValidationResult<()>;
pub type StringResult = ValidationResult<String>;
pub type NumericResult<T> = ValidationResult<T>;
pub type SchemaResult = ValidationResult<JsonValue>;

/// **VALIDATION CONTEXT**
///
/// **PURPOSE**: Provides runtime context for validation operations.
/// **USAGE**: Pass to validators requiring contextual information.
#[derive(Debug, Clone)]
pub struct ValidationContext {
    /// **MAXIMUM BUFFER SIZE** - Global limit for buffer validation
    pub max_buffer_size: usize,
    
    /// **STRICT MODE** - Enable additional validation checks
    pub strict_mode: bool,
    
    /// **CUSTOM CONSTRAINTS** - User-defined validation parameters
    pub custom_constraints: HashMap<String, JsonValue>,
}

impl Default for ValidationContext {
    fn default() -> Self {
        Self {
            max_buffer_size: 10_485_760, // 10MB default limit
            strict_mode: false,
            custom_constraints: HashMap::new(),
        }
    }
}

/// **VALIDATION ERROR CODES**
///
/// **MANDATE**: Use these standardized error codes for consistent error reporting.
pub mod error_codes {
    pub const BUFFER_TOO_LARGE: &str = "RUST_CORE_VALIDATION_BUFFER_TOO_LARGE";
    pub const INVALID_UTF8: &str = "RUST_CORE_VALIDATION_INVALID_UTF8";
    pub const OUT_OF_RANGE: &str = "RUST_CORE_VALIDATION_OUT_OF_RANGE";
    pub const SCHEMA_MISMATCH: &str = "RUST_CORE_VALIDATION_SCHEMA_MISMATCH";
    pub const INVALID_INPUT: &str = "RUST_CORE_VALIDATION_INVALID_INPUT";
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validation_context_default() {
        let ctx = ValidationContext::default();
        assert_eq!(ctx.max_buffer_size, 10_485_760);
        assert!(!ctx.strict_mode);
        assert!(ctx.custom_constraints.is_empty());
    }

    #[test]
    fn test_validation_context_custom() {
        let mut ctx = ValidationContext::default();
        ctx.max_buffer_size = 1024;
        ctx.strict_mode = true;
        ctx.custom_constraints.insert(
            "test_key".to_string(),
            JsonValue::String("test_value".to_string())
        );

        assert_eq!(ctx.max_buffer_size, 1024);
        assert!(ctx.strict_mode);
        assert_eq!(ctx.custom_constraints.len(), 1);
    }

    #[test]
    fn test_error_codes_exist() {
        assert!(!error_codes::BUFFER_TOO_LARGE.is_empty());
        assert!(!error_codes::INVALID_UTF8.is_empty());
        assert!(!error_codes::OUT_OF_RANGE.is_empty());
        assert!(!error_codes::SCHEMA_MISMATCH.is_empty());
        assert!(!error_codes::INVALID_INPUT.is_empty());
    }
}
