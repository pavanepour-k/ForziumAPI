use forzium::api::*;
use forzium::errors::ProjectError;

#[test]
fn test_validate_buffer_integration() {
    let data = vec![0u8; 1000];
    assert!(validate_buffer_size(&data).is_ok());

    let max_data = vec![0u8; 10_485_760];
    assert!(validate_buffer_size(&max_data).is_ok());

    let too_large = vec![0u8; 10_485_761];
    assert!(matches!(
        validate_buffer_size(&too_large),
        Err(ProjectError::Validation { .. })
    ));
}

#[test]
fn test_validate_utf8_integration() {
    let ascii = b"Hello, world!";
    let result = validate_utf8_string(ascii).unwrap();
    assert_eq!(result, "Hello, world!");

    let unicode = "あゝ青い風 ".as_bytes();
    let result = validate_utf8_string(unicode).unwrap();
    assert_eq!(result, "あゝ青い風 ");

    let invalid = &[0xFF, 0xFE, 0xFD];
    assert!(matches!(
        validate_utf8_string(invalid),
        Err(ProjectError::Validation { .. })
    ));
}

#[test]
fn test_validate_u8_range_integration() {
    for i in 0..=255u8 {
        assert!(validate_u8_range(i).is_ok());
    }
}
