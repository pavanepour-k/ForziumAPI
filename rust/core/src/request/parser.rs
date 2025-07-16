use crate::errors::ProjectError;
use std::collections::HashMap;

pub fn parse_query_string(query: &str) -> HashMap<String, String> {
    query
        .split('&')
        .filter_map(|pair| {
            let mut parts = pair.split('=');
            match (parts.next(), parts.next()) {
                (Some(key), Some(value)) => Some((
                    urlencoding::decode(key).ok()?.into_owned(),
                    urlencoding::decode(value).ok()?.into_owned(),
                )),
                _ => None,
            }
        })
        .collect()
}

pub fn parse_json_body(data: &[u8]) -> Result<serde_json::Value, ProjectError> {
    serde_json::from_slice(data).map_err(|e| ProjectError::Validation {
        code: "RUST_CORE_VALIDATION_INVALID_JSON".to_string(),
        message: format!("Invalid JSON: {}", e),
    })
}

pub fn parse_form_body(data: &[u8]) -> Result<HashMap<String, String>, ProjectError> {
    let body_str = std::str::from_utf8(data).map_err(|e| ProjectError::Validation {
        code: "RUST_CORE_VALIDATION_INVALID_UTF8".to_string(),
        message: format!("Invalid UTF-8 in form body: {}", e),
    })?;

    Ok(parse_query_string(body_str))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_query_string_simple() {
        let query = "key1=value1&key2=value2";
        let result = parse_query_string(query);
        assert_eq!(result.get("key1"), Some(&"value1".to_string()));
        assert_eq!(result.get("key2"), Some(&"value2".to_string()));
    }

    #[test]
    fn test_parse_query_string_encoded() {
        let query = "name=John%20Doe&city=New%20York";
        let result = parse_query_string(query);
        assert_eq!(result.get("name"), Some(&"John Doe".to_string()));
        assert_eq!(result.get("city"), Some(&"New York".to_string()));
    }

    #[test]
    fn test_parse_query_string_empty() {
        let query = "";
        let result = parse_query_string(query);
        assert!(result.is_empty());
    }

    #[test]
    fn test_parse_json_body_valid() {
        let json_data = br#"{"name": "test", "value": 42}"#;
        let result = parse_json_body(json_data).unwrap();
        assert_eq!(result["name"], "test");
        assert_eq!(result["value"], 42);
    }

    #[test]
    fn test_parse_json_body_invalid() {
        let json_data = br#"{"name": "test", invalid}"#;
        let result = parse_json_body(json_data);
        assert!(result.is_err());
    }
}
