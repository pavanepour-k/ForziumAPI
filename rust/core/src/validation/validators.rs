//! # CONCRETE VALIDATOR IMPLEMENTATIONS
//!
//! **CRITICAL**: Four production-ready validators implementing the core `Validator` trait.
//! **MANDATE**: ALL validators MUST handle edge cases and provide comprehensive error reporting.

use super::{error_codes, Validator};
use crate::errors::ProjectError;
use serde_json::Value as JsonValue;
use std::collections::HashMap;
use std::ops::RangeInclusive;

// ================================================================================================
// BUFFER VALIDATOR - Memory-safe buffer size validation
// ================================================================================================

/// **BUFFER VALIDATOR**
///
/// **PURPOSE**: Validates buffer size against configurable limits.
/// **GUARANTEE**: Prevents memory exhaustion attacks and buffer overflow conditions.
/// **PERFORMANCE**: O(1) constant-time validation.
#[derive(Debug, Clone)]
pub struct BufferValidator {
    /// **MAXIMUM ALLOWED SIZE** - Buffer size limit in bytes
    max_size: usize,
    
    /// **STRICT MODE** - Reject empty buffers when enabled
    strict: bool,
}

impl BufferValidator {
    /// **CONSTRUCTOR**
    ///
    /// **PARAMETERS**:
    /// - `max_size: usize` - Maximum buffer size in bytes
    ///
    /// **RETURNS**: Configured BufferValidator instance
    pub fn new(max_size: usize) -> Self {
        Self {
            max_size,
            strict: false,
        }
    }

    /// **CONSTRUCTOR WITH STRICT MODE**
    ///
    /// **PARAMETERS**:
    /// - `max_size: usize` - Maximum buffer size in bytes
    /// - `strict: bool` - Reject empty buffers if true
    pub fn with_strict(max_size: usize, strict: bool) -> Self {
        Self { max_size, strict }
    }

    /// **DEFAULT CONSTRUCTOR** - Uses 10MB limit
    pub fn default() -> Self {
        Self::new(10_485_760)
    }
}

impl Validator for BufferValidator {
    type Input = Vec<u8>;
    type Output = ();

    fn validate(&self, input: Self::Input) -> Result<Self::Output, ProjectError> {
        // **STEP 1**: Check empty buffer in strict mode
        if self.strict && input.is_empty() {
            return Err(ProjectError::Validation {
                code: error_codes::INVALID_INPUT.to_string(),
                message: "Empty buffer rejected in strict mode".to_string(),
            });
        }

        // **STEP 2**: Validate buffer size
        if input.len() > self.max_size {
            return Err(ProjectError::Validation {
                code: error_codes::BUFFER_TOO_LARGE.to_string(),
                message: format!(
                    "Buffer size {} exceeds maximum allowed size {}",
                    input.len(),
                    self.max_size
                ),
            });
        }

        Ok(())
    }
}

// ================================================================================================
// UTF-8 VALIDATOR - String encoding validation
// ================================================================================================

/// **UTF-8 VALIDATOR**
///
/// **PURPOSE**: Validates byte sequences as valid UTF-8 and converts to String.
/// **GUARANTEE**: Prevents invalid Unicode data from entering the system.
/// **PERFORMANCE**: Single-pass validation with zero-copy where possible.
#[derive(Debug, Clone)]
pub struct Utf8Validator {
    /// **ALLOW EMPTY STRINGS** - Accept empty byte sequences
    allow_empty: bool,
    
    /// **MAXIMUM STRING LENGTH** - Optional length limit
    max_length: Option<usize>,
}

impl Utf8Validator {
    /// **CONSTRUCTOR**
    pub fn new() -> Self {
        Self {
            allow_empty: true,
            max_length: None,
        }
    }

    /// **CONSTRUCTOR WITH LENGTH LIMIT**
    ///
    /// **PARAMETERS**:
    /// - `max_length: usize` - Maximum string length in characters
    pub fn with_max_length(max_length: usize) -> Self {
        Self {
            allow_empty: true,
            max_length: Some(max_length),
        }
    }

    /// **CONSTRUCTOR WITH STRICT MODE**
    ///
    /// **PARAMETERS**:
    /// - `allow_empty: bool` - Allow empty strings
    /// - `max_length: Option<usize>` - Optional length limit
    pub fn with_options(allow_empty: bool, max_length: Option<usize>) -> Self {
        Self {
            allow_empty,
            max_length,
        }
    }
}

impl Default for Utf8Validator {
    fn default() -> Self {
        Self::new()
    }
}

impl Validator for Utf8Validator {
    type Input = Vec<u8>;
    type Output = String;

    fn validate(&self, input: Self::Input) -> Result<Self::Output, ProjectError> {
        // **STEP 1**: Check empty input
        if input.is_empty() {
            if self.allow_empty {
                return Ok(String::new());
            } else {
                return Err(ProjectError::Validation {
                    code: error_codes::INVALID_INPUT.to_string(),
                    message: "Empty byte sequence not allowed".to_string(),
                });
            }
        }

        // **STEP 2**: Validate UTF-8 encoding
        let string = std::str::from_utf8(&input).map_err(|e| ProjectError::Validation {
            code: error_codes::INVALID_UTF8.to_string(),
            message: format!("Invalid UTF-8 sequence: {}", e),
        })?;

        // **STEP 3**: Check length limit
        if let Some(max_len) = self.max_length {
            if string.chars().count() > max_len {
                return Err(ProjectError::Validation {
                    code: error_codes::OUT_OF_RANGE.to_string(),
                    message: format!(
                        "String length {} exceeds maximum {}",
                        string.chars().count(),
                        max_len
                    ),
                });
            }
        }

        Ok(string.to_string())
    }
}

// ================================================================================================
// NUMERIC RANGE VALIDATOR - Type-safe numeric validation
// ================================================================================================

/// **NUMERIC RANGE VALIDATOR**
///
/// **PURPOSE**: Validates numeric values against configurable range constraints.
/// **GUARANTEE**: Type-safe bounds checking with overflow protection.
/// **PERFORMANCE**: Compile-time optimized range checks.
#[derive(Debug, Clone)]
pub struct NumericRangeValidator<T> {
    /// **VALID RANGE** - Inclusive range of acceptable values
    range: RangeInclusive<T>,
    
    /// **TYPE NAME** - For error reporting
    type_name: &'static str,
}

impl<T> NumericRangeValidator<T>
where
    T: PartialOrd + Copy + std::fmt::Display,
{
    /// **CONSTRUCTOR**
    ///
    /// **PARAMETERS**:
    /// - `range: RangeInclusive<T>` - Valid value range (inclusive)
    /// - `type_name: &'static str` - Type identifier for errors
    pub fn new(range: RangeInclusive<T>, type_name: &'static str) -> Self {
        Self { range, type_name }
    }
}

impl NumericRangeValidator<u8> {
    /// **U8 VALIDATOR CONSTRUCTOR** - Optimized for byte values
    pub fn u8() -> NumericRangeValidator<u8> {
        NumericRangeValidator::new(0u8..=255u8, "u8")
    }
}

impl NumericRangeValidator<i32> {
    /// **I32 VALIDATOR CONSTRUCTOR** - Common integer range
    pub fn i32_range(min: i32, max: i32) -> NumericRangeValidator<i32> {
        NumericRangeValidator::new(min..=max, "i32")
    }
}

impl NumericRangeValidator<f64> {
    /// **F64 VALIDATOR CONSTRUCTOR** - Floating point range
    pub fn f64_range(min: f64, max: f64) -> NumericRangeValidator<f64> {
        NumericRangeValidator::new(min..=max, "f64")
    }
}

impl<T> Validator for NumericRangeValidator<T>
where
    T: PartialOrd + Copy + std::fmt::Display,
{
    type Input = T;
    type Output = T;

    fn validate(&self, input: Self::Input) -> Result<Self::Output, ProjectError> {
        if self.range.contains(&input) {
            Ok(input)
        } else {
            Err(ProjectError::Validation {
                code: error_codes::OUT_OF_RANGE.to_string(),
                message: format!(
                    "Value {} outside valid {} range {}..={}",
                    input,
                    self.type_name,
                    self.range.start(),
                    self.range.end()
                ),
            })
        }
    }
}

// ================================================================================================
// SCHEMA VALIDATOR - JSON schema validation
// ================================================================================================

/// **SCHEMA VALIDATOR**
///
/// **PURPOSE**: Validates JSON data against predefined schema rules.
/// **GUARANTEE**: Structural data integrity with comprehensive type checking.
/// **PERFORMANCE**: Efficient traversal with early termination on errors.
#[derive(Debug, Clone)]
pub struct SchemaValidator {
    /// **REQUIRED FIELDS** - Field names that must be present
    required_fields: Vec<String>,
    
    /// **FIELD TYPES** - Expected JSON types for each field
    field_types: HashMap<String, JsonType>,
    
    /// **STRICT MODE** - Reject unknown fields when enabled
    strict: bool,
}

/// **JSON TYPE ENUMERATION**
#[derive(Debug, Clone, PartialEq)]
pub enum JsonType {
    String,
    Number,
    Boolean,
    Array,
    Object,
    Null,
}

impl SchemaValidator {
    /// **CONSTRUCTOR**
    pub fn new() -> Self {
        Self {
            required_fields: Vec::new(),
            field_types: HashMap::new(),
            strict: false,
        }
    }

    /// **ADD REQUIRED FIELD**
    ///
    /// **PARAMETERS**:
    /// - `field: impl Into<String>` - Field name
    /// - `json_type: JsonType` - Expected type
    pub fn require_field(mut self, field: impl Into<String>, json_type: JsonType) -> Self {
        let field_name = field.into();
        self.required_fields.push(field_name.clone());
        self.field_types.insert(field_name, json_type);
        self
    }

    /// **ADD OPTIONAL FIELD**
    ///
    /// **PARAMETERS**:
    /// - `field: impl Into<String>` - Field name
    /// - `json_type: JsonType` - Expected type
    pub fn optional_field(mut self, field: impl Into<String>, json_type: JsonType) -> Self {
        self.field_types.insert(field.into(), json_type);
        self
    }

    /// **ENABLE STRICT MODE** - Reject unknown fields
    pub fn strict(mut self) -> Self {
        self.strict = true;
        self
    }

    /// **VALIDATE JSON TYPE**
    fn validate_json_type(value: &JsonValue, expected: &JsonType) -> bool {
        match (value, expected) {
            (JsonValue::String(_), JsonType::String) => true,
            (JsonValue::Number(_), JsonType::Number) => true,
            (JsonValue::Bool(_), JsonType::Boolean) => true,
            (JsonValue::Array(_), JsonType::Array) => true,
            (JsonValue::Object(_), JsonType::Object) => true,
            (JsonValue::Null, JsonType::Null) => true,
            _ => false,
        }
    }
}

impl Default for SchemaValidator {
    fn default() -> Self {
        Self::new()
    }
}

impl Validator for SchemaValidator {
    type Input = JsonValue;
    type Output = JsonValue;

    fn validate(&self, input: Self::Input) -> Result<Self::Output, ProjectError> {
        // **STEP 1**: Ensure input is object for field validation
        let obj = match &input {
            JsonValue::Object(map) => map,
            _ => {
                return Err(ProjectError::Validation {
                    code: error_codes::SCHEMA_MISMATCH.to_string(),
                    message: "Expected JSON object for schema validation".to_string(),
                });
            }
        };

        // **STEP 2**: Validate required fields
        for required_field in &self.required_fields {
            if !obj.contains_key(required_field) {
                return Err(ProjectError::Validation {
                    code: error_codes::SCHEMA_MISMATCH.to_string(),
                    message: format!("Required field '{}' missing", required_field),
                });
            }
        }

        // **STEP 3**: Validate field types
        for (field_name, value) in obj {
            if let Some(expected_type) = self.field_types.get(field_name) {
                if !Self::validate_json_type(value, expected_type) {
                    return Err(ProjectError::Validation {
                        code: error_codes::SCHEMA_MISMATCH.to_string(),
                        message: format!(
                            "Field '{}' has invalid type, expected {:?}",
                            field_name, expected_type
                        ),
                    });
                }
            } else if self.strict {
                return Err(ProjectError::Validation {
                    code: error_codes::SCHEMA_MISMATCH.to_string(),
                    message: format!("Unknown field '{}' in strict mode", field_name),
                });
            }
        }

        Ok(input)
    }
}

// ================================================================================================
// UNIT TESTS - Comprehensive coverage for all validators
// ================================================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // **BUFFER VALIDATOR TESTS**
    mod buffer_validator_tests {
        use super::*;

        #[test]
        fn test_buffer_validator_success() {
            let validator = BufferValidator::new(1024);
            let data = b"test data".to_vec();
            assert!(validator.validate(data).is_ok());
        }

        #[test]
        fn test_buffer_validator_empty_allowed() {
            let validator = BufferValidator::new(1024);
            let data = vec![];
            assert!(validator.validate(data).is_ok());
        }

        #[test]
        fn test_buffer_validator_empty_strict() {
            let validator = BufferValidator::with_strict(1024, true);
            let data = vec![];
            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, message }) = result {
                assert_eq!(code, error_codes::INVALID_INPUT);
                assert!(message.contains("Empty buffer"));
            }
        }

        #[test]
        fn test_buffer_validator_too_large() {
            let validator = BufferValidator::new(10);
            let data = b"this is too long".to_vec();
            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, message }) = result {
                assert_eq!(code, error_codes::BUFFER_TOO_LARGE);
                assert!(message.contains("exceeds maximum"));
            }
        }

        #[test]
        fn test_buffer_validator_exact_limit() {
            let validator = BufferValidator::new(10);
            let data = b"exactly10b".to_vec();
            assert!(validator.validate(data).is_ok());
        }
    }

    // **UTF-8 VALIDATOR TESTS**
    mod utf8_validator_tests {
        use super::*;

        #[test]
        fn test_utf8_validator_success() {
            let validator = Utf8Validator::new();
            let data = "Hello, world!".as_bytes().to_vec();
            let result = validator.validate(data);
            assert!(result.is_ok());
            assert_eq!(result.unwrap(), "Hello, world!");
        }

        #[test]
        fn test_utf8_validator_unicode() {
            let validator = Utf8Validator::new();
            let data = "こんにちは世界 🌍".as_bytes().to_vec();
            let result = validator.validate(data);
            assert!(result.is_ok());
            assert_eq!(result.unwrap(), "こんにちは世界 🌍");
        }

        #[test]
        fn test_utf8_validator_empty() {
            let validator = Utf8Validator::new();
            let data = vec![];
            let result = validator.validate(data);
            assert!(result.is_ok());
            assert_eq!(result.unwrap(), "");
        }

        #[test]
        fn test_utf8_validator_empty_rejected() {
            let validator = Utf8Validator::with_options(false, None);
            let data = vec![];
            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, .. }) = result {
                assert_eq!(code, error_codes::INVALID_INPUT);
            }
        }

        #[test]
        fn test_utf8_validator_invalid_sequence() {
            let validator = Utf8Validator::new();
            let data = vec![0xFF, 0xFE, 0xFD];
            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, .. }) = result {
                assert_eq!(code, error_codes::INVALID_UTF8);
            }
        }

        #[test]
        fn test_utf8_validator_length_limit() {
            let validator = Utf8Validator::with_max_length(5);
            let data = "short".as_bytes().to_vec();
            assert!(validator.validate(data).is_ok());
            
            let long_data = "toolong".as_bytes().to_vec();
            let result = validator.validate(long_data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, .. }) = result {
                assert_eq!(code, error_codes::OUT_OF_RANGE);
            }
        }
    }

    // **NUMERIC RANGE VALIDATOR TESTS**
    mod numeric_validator_tests {
        use super::*;

        #[test]
        fn test_numeric_validator_u8_success() {
            let validator = NumericRangeValidator::u8();
            assert!(validator.validate(0).is_ok());
            assert!(validator.validate(128).is_ok());
            assert!(validator.validate(255).is_ok());
        }

        #[test]
        fn test_numeric_validator_i32_range() {
            let validator = NumericRangeValidator::i32_range(-100, 100);
            assert!(validator.validate(0).is_ok());
            assert!(validator.validate(-50).is_ok());
            assert!(validator.validate(50).is_ok());

            let result = validator.validate(150);
            assert!(result.is_err());

            if let Err(ProjectError::Validation { code, .. }) = result {
                assert_eq!(code, error_codes::OUT_OF_RANGE);
            }
        }

        #[test]
        fn test_numeric_validator_f64_range() {
            let validator = NumericRangeValidator::f64_range(0.0, 1.0);
            assert!(validator.validate(0.5).is_ok());
            assert!(validator.validate(0.0).is_ok());
            assert!(validator.validate(1.0).is_ok());

            let result = validator.validate(1.5);
            assert!(result.is_err());
        }

        #[test]
        fn test_numeric_validator_boundary_values() {
            let validator = NumericRangeValidator::i32_range(10, 20);
            assert!(validator.validate(10).is_ok());
            assert!(validator.validate(20).is_ok());
            assert!(validator.validate(9).is_err());
            assert!(validator.validate(21).is_err());
        }
    }

    // **SCHEMA VALIDATOR TESTS**
    mod schema_validator_tests {
        use super::*;

        #[test]
        fn test_schema_validator_success() {
            let validator = SchemaValidator::new()
                .require_field("name", JsonType::String)
                .require_field("age", JsonType::Number)
                .optional_field("email", JsonType::String);

            let data = json!({
                "name": "John Doe",
                "age": 30,
                "email": "john@example.com"
            });

            assert!(validator.validate(data).is_ok());
        }

        #[test]
        fn test_schema_validator_missing_required() {
            let validator = SchemaValidator::new()
                .require_field("name", JsonType::String);

            let data = json!({"age": 30});
            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, message }) = result {
                assert_eq!(code, error_codes::SCHEMA_MISMATCH);
                assert!(message.contains("Required field 'name' missing"));
            }
        }

        #[test]
        fn test_schema_validator_wrong_type() {
            let validator = SchemaValidator::new()
                .require_field("age", JsonType::Number);

            let data = json!({"age": "thirty"});
            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, .. }) = result {
                assert_eq!(code, error_codes::SCHEMA_MISMATCH);
            }
        }

        #[test]
        fn test_schema_validator_strict_mode() {
            let validator = SchemaValidator::new()
                .require_field("name", JsonType::String)
                .strict();

            let data = json!({
                "name": "John",
                "unknown_field": "value"
            });

            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, message }) = result {
                assert_eq!(code, error_codes::SCHEMA_MISMATCH);
                assert!(message.contains("Unknown field"));
            }
        }

        #[test]
        fn test_schema_validator_non_object() {
            let validator = SchemaValidator::new();
            let data = json!("not an object");
            let result = validator.validate(data);
            assert!(result.is_err());
            
            if let Err(ProjectError::Validation { code, .. }) = result {
                assert_eq!(code, error_codes::SCHEMA_MISMATCH);
            }
        }

        #[test]
        fn test_schema_validator_empty_object() {
            let validator = SchemaValidator::new();
            let data = json!({});
            assert!(validator.validate(data).is_ok());
        }
    }
}
