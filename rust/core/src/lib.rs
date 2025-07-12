pub mod api;
pub mod errors;
pub mod types;

mod validation;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::api::*;
    use crate::errors::ProjectError;

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
                assert_eq!(code, "RUST_CORE_VALIDATION_BUFFER_TOO_LARGE");
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
        let data = "天城越え 🌍".as_bytes();
        let result = validate_utf8_string(data);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "天城越え 🌍");
    }

    #[test]
    fn test_validate_utf8_string_invalid() {
        let data = &[0xFF, 0xFE, 0xFD];
        let result = validate_utf8_string(data);
        assert!(result.is_err());
        
        match result.unwrap_err() {
            ProjectError::Validation { code, message } => {
                assert_eq!(code, "RUST_CORE_VALIDATION_INVALID_UTF8");
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
}
