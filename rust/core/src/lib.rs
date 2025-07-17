//! # FORZIUM CORE LIBRARY
//!
//! **RUST-POWERED FASTAPI REPLACEMENT CORE COMPONENTS**
//!
//! **ARCHITECTURE**: Modular design with trait-based validation system
//! **GUARANTEE**: Memory-safe, high-performance request processing
//! **COMPATIBILITY**: Seamless Python FFI integration via PyO3

pub mod api;
pub mod dependencies;
pub mod errors;
pub mod request;
pub mod response;
pub mod routing;
pub mod types;

// **VALIDATION MODULE REGISTRATION**
pub mod validation;

#[cfg(test)]
mod tests {
    use crate::api::*;
    use crate::errors::ProjectError;
    use crate::validation::{
        BufferValidator, NumericRangeValidator, SchemaValidator, Utf8Validator, Validator,
        JsonType,
    };
    use serde_json::json;

    // **LEGACY VALIDATION FUNCTION TESTS**
    #[test]
    fn test_validate_buffer_size_success() {
        let data = vec![0u8; 1024];
        assert!(validate_buffer_size(&data).is_ok());
    }

    #[test]
    fn test_validate_buffer_size_empty() {
        let data = vec![];
        assert!(validate_buffer_size(&data).is_ok());
    }

    #[test]
    fn test_validate_buffer_size_max_allowed() {
        let data = vec![0u8; 10_485_760];
        assert!(validate_buffer_size(&data).is_ok());
    }

    #[test]
    fn test_validate_buffer_size_too_large() {
        let data = vec![0u8; 10_485_761];
        let result = validate_buffer_size(&data);
        assert!(result.is_err());

        match result.unwrap_err() {
            ProjectError::Validation { code, message } => {
                assert!(code.contains("BUFFER_TOO_LARGE"));
                assert!(message.contains("10485761"));
                assert!(message.contains("10485760"));
            }
            _ => panic!("Wrong error type"),
        }
    }

    #[test]
    fn test_validate_utf8_string_success() {
        let data = "Hello, world!".as_bytes();
        let result = validate_utf8_string(data);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "Hello, world!");
    }

    #[test]
    fn test_validate_utf8_string_empty() {
        let data = b"";
        let result = validate_utf8_string(data);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "");
    }

    #[test]
    fn test_validate_utf8_string_unicode() {
        let data = "隠しきれない".as_bytes();
        let result = validate_utf8_string(data);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "隠しきれない");
    }

    #[test]
    fn test_validate_utf8_string_invalid() {
        let data = &[0xFF, 0xFE, 0xFD];
        let result = validate_utf8_string(data);
        assert!(result.is_err());

        match result.unwrap_err() {
            ProjectError::Validation { code, message } => {
                assert!(code.contains("INVALID_UTF8"));
                assert!(message.contains("Invalid UTF-8"));
            }
            _ => panic!("Wrong error type"),
        }
    }

    #[test]
    fn test_validate_u8_range_min() {
        assert!(validate_u8_range(0).is_ok());
    }

    #[test]
    fn test_validate_u8_range_max() {
        assert!(validate_u8_range(255).is_ok());
    }

    #[test]
    fn test_validate_u8_range_mid() {
        assert!(validate_u8_range(128).is_ok());
    }

    // **NEW TRAIT-BASED VALIDATOR TESTS**
    #[test]
    fn test_buffer_validator_trait() {
        let validator = BufferValidator::new(1024);
        let data = b"test data".to_vec();
        assert!(validator.validate(data).is_ok());
    }

    #[test]
    fn test_utf8_validator_trait() {
        let validator = Utf8Validator::new();
        let data = "Hello, trait!".as_bytes().to_vec();
        let result = validator.validate(data);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "Hello, trait!");
    }

    #[test]
    fn test_numeric_validator_trait() {
        let validator = NumericRangeValidator::u8();
        assert!(validator.validate(128).is_ok());
        assert_eq!(validator.validate(200).unwrap(), 200);
    }

    #[test]
    fn test_schema_validator_trait() {
        let validator = SchemaValidator::new()
            .require_field("name", JsonType::String)
            .require_field("age", JsonType::Number);

        let data = json!({
            "name": "John Doe",
            "age": 30
        });

        let result = validator.validate(data.clone());
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), data);
    }

    // **INTEGRATION TESTS**
    #[test]
    fn test_validation_pipeline() {
        // **STEP 1**: Validate buffer size
        let raw_data = r#"{"message": "Hello, 世界!"}"#.as_bytes();
        assert!(validate_buffer_size(raw_data).is_ok());

        // **STEP 2**: Validate UTF-8 encoding
        let utf8_result = validate_utf8_string(raw_data);
        assert!(utf8_result.is_ok());
        let json_string = utf8_result.unwrap();

        // **STEP 3**: Parse and validate JSON schema
        let json_value: serde_json::Value = serde_json::from_str(&json_string).unwrap();
        let schema_validator = SchemaValidator::new()
            .require_field("message", JsonType::String);

        let schema_result = schema_validator.validate(json_value);
        assert!(schema_result.is_ok());
    }

    #[test]
    fn test_validation_error_propagation() {
        // **TEST**: Ensure errors propagate correctly through validation chain
        let invalid_data = vec![0u8; 10_485_761]; // Too large
        let buffer_result = validate_buffer_size(&invalid_data);
        assert!(buffer_result.is_err());

        match buffer_result.unwrap_err() {
            ProjectError::Validation { code, .. } => {
                assert!(code.contains("BUFFER_TOO_LARGE"));
            }
            _ => panic!("Expected validation error"),
        }
    }
}
