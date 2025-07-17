use crate::response::{HttpResponse, ResponseBody, create_response, serialize_json_response, serialize_response_body};
use serde_json::json;

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    // **JSON RESPONSE TESTS**
    #[test]
    fn test_create_json_response() {
        let body = ResponseBody::Json(json!({"status": "ok", "count": 42}));
        let response = create_response(200, body);

        assert_eq!(response.status_code, 200);
        assert_eq!(
            response.headers.get("Content-Type"),
            Some(&"application/json".to_string())
        );
        
        match &response.body {
            ResponseBody::Json(value) => {
                assert_eq!(value["status"], "ok");
                assert_eq!(value["count"], 42);
            }
            _ => panic!("Expected JSON body"),
        }
    }

    #[test]
    fn test_create_text_response() {
        let body = ResponseBody::Text("Hello, World!".to_string());
        let response = create_response(201, body);

        assert_eq!(response.status_code, 201);
        assert_eq!(
            response.headers.get("Content-Type"),
            Some(&"text/plain".to_string())
        );
        
        match &response.body {
            ResponseBody::Text(text) => assert_eq!(text, "Hello, World!"),
            _ => panic!("Expected Text body"),
        }
    }

    #[test]
    fn test_create_binary_response() {
        let body = ResponseBody::Binary(vec![0xFF, 0xFE, 0xFD]);
        let response = create_response(202, body);

        assert_eq!(response.status_code, 202);
        assert_eq!(
            response.headers.get("Content-Type"),
            Some(&"application/octet-stream".to_string())
        );
        
        match &response.body {
            ResponseBody::Binary(data) => assert_eq!(data, &vec![0xFF, 0xFE, 0xFD]),
            _ => panic!("Expected Binary body"),
        }
    }

    #[test]
    fn test_create_empty_response() {
        let body = ResponseBody::Empty;
        let response = create_response(204, body);

        assert_eq!(response.status_code, 204);
        assert!(response.headers.get("Content-Type").is_none());
        
        match response.body {
            ResponseBody::Empty => (),
            _ => panic!("Expected Empty body"),
        }
    }

    // **SERIALIZATION TESTS**
    #[test]
    fn test_serialize_json_simple() {
        let value = json!({"test": "data"});
        let serialized = serialize_json_response(&value);
        
        assert!(!serialized.is_empty());
        
        // Verify it can be deserialized back
        let deserialized: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
        assert_eq!(deserialized, value);
    }

    #[test]
    fn test_serialize_json_complex() {
        let value = json!({
            "users": [
                {"id": 1, "name": "Alice", "active": true},
                {"id": 2, "name": "Bob", "active": false}
            ],
            "meta": {
                "count": 2,
                "page": 1,
                "total": 100
            },
            "timestamp": "2024-01-01T00:00:00Z"
        });
        
        let serialized = serialize_json_response(&value);
        assert!(!serialized.is_empty());
        
        let deserialized: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
        assert_eq!(deserialized["users"].as_array().unwrap().len(), 2);
        assert_eq!(deserialized["meta"]["count"], 2);
    }

    #[test]
    fn test_serialize_json_unicode() {
        let value = json!({
            "message": "Hello, 世界! 🌍",
            "japanese": "こんにちは",
            "emoji": "🚀🎉✨"
        });
        
        let serialized = serialize_json_response(&value);
        let deserialized: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
        
        assert_eq!(deserialized["message"], "Hello, 世界! 🌍");
        assert_eq!(deserialized["japanese"], "こんにちは");
        assert_eq!(deserialized["emoji"], "🚀🎉✨");
    }

    #[test]
    fn test_serialize_json_null_values() {
        let value = json!({
            "name": "Test",
            "optional": null,
            "nested": {
                "value": null
            }
        });
        
        let serialized = serialize_json_response(&value);
        let deserialized: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
        
        assert_eq!(deserialized["name"], "Test");
        assert!(deserialized["optional"].is_null());
        assert!(deserialized["nested"]["value"].is_null());
    }

    #[test]
    fn test_serialize_response_body_json() {
        let body = ResponseBody::Json(json!({"key": "value"}));
        let serialized = serialize_response_body(&body);
        
        assert!(!serialized.is_empty());
        let expected = br#"{"key":"value"}"#;
        assert_eq!(serialized, expected);
    }

    #[test]
    fn test_serialize_response_body_text() {
        let body = ResponseBody::Text("Plain text response".to_string());
        let serialized = serialize_response_body(&body);
        
        assert_eq!(serialized, b"Plain text response");
    }

    #[test]
    fn test_serialize_response_body_binary() {
        let data = vec![0x00, 0x01, 0x02, 0xFF];
        let body = ResponseBody::Binary(data.clone());
        let serialized = serialize_response_body(&body);
        
        assert_eq!(serialized, data);
    }

    #[test]
    fn test_serialize_response_body_empty() {
        let body = ResponseBody::Empty;
        let serialized = serialize_response_body(&body);
        
        assert!(serialized.is_empty());
    }

    // **ERROR CASE TESTS**
    #[test]
    fn test_error_response_creation() {
        let error_body = ResponseBody::Json(json!({
            "error": "Invalid request",
            "code": "VALIDATION_ERROR",
            "details": {
                "field": "email",
                "message": "Invalid email format"
            }
        }));
        
        let response = create_response(400, error_body);
        
        assert_eq!(response.status_code, 400);
        match &response.body {
            ResponseBody::Json(value) => {
                assert_eq!(value["error"], "Invalid request");
                assert_eq!(value["code"], "VALIDATION_ERROR");
                assert_eq!(value["details"]["field"], "email");
            }
            _ => panic!("Expected JSON error body"),
        }
    }

    // **LARGE PAYLOAD TESTS**
    #[test]
    fn test_serialize_large_json_array() {
        let mut items = Vec::new();
        for i in 0..1000 {
            items.push(json!({
                "id": i,
                "data": format!("Item {}", i),
                "tags": vec!["tag1", "tag2", "tag3"]
            }));
        }
        
        let value = json!({"items": items});
        let serialized = serialize_json_response(&value);
        
        assert!(!serialized.is_empty());
        
        let deserialized: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
        assert_eq!(deserialized["items"].as_array().unwrap().len(), 1000);
    }

    #[test]
    fn test_serialize_large_text() {
        let large_text = "Lorem ipsum ".repeat(1000);
        let body = ResponseBody::Text(large_text.clone());
        let serialized = serialize_response_body(&body);
        
        assert_eq!(serialized.len(), large_text.len());
        assert_eq!(serialized, large_text.as_bytes());
    }

    // **EDGE CASE TESTS**
    #[test]
    fn test_empty_json_object() {
        let value = json!({});
        let serialized = serialize_json_response(&value);
        assert_eq!(serialized, b"{}");
    }

    #[test]
    fn test_empty_json_array() {
        let value = json!([]);
        let serialized = serialize_json_response(&value);
        assert_eq!(serialized, b"[]");
    }

    #[test]
    fn test_special_characters_in_json() {
        let value = json!({
            "special": "Line1\nLine2\tTabbed",
            "quotes": "She said \"Hello\"",
            "backslash": "C:\\Windows\\System32",
            "unicode": "\u{1F600}"  // 😀
        });
        
        let serialized = serialize_json_response(&value);
        let deserialized: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
        
        assert!(deserialized["special"].as_str().unwrap().contains('\n'));
        assert!(deserialized["quotes"].as_str().unwrap().contains('"'));
        assert!(deserialized["backslash"].as_str().unwrap().contains('\\'));
    }

    // **CUSTOM HEADER TESTS**
    #[test]
    fn test_response_with_custom_headers() {
        let mut response = create_response(200, ResponseBody::Empty);
        response.headers.insert("X-Custom-Header".to_string(), "custom-value".to_string());
        response.headers.insert("X-Request-ID".to_string(), "12345".to_string());
        
        assert_eq!(response.headers.get("X-Custom-Header"), Some(&"custom-value".to_string()));
        assert_eq!(response.headers.get("X-Request-ID"), Some(&"12345".to_string()));
    }

    // **INTEGRATION TESTS**
    #[test]
    fn test_full_response_cycle() {
        // Create a complex response
        let data = json!({
            "success": true,
            "data": {
                "user": {
                    "id": 123,
                    "name": "Test User",
                    "email": "test@example.com"
                },
                "permissions": ["read", "write", "admin"]
            },
            "meta": {
                "timestamp": "2024-01-01T00:00:00Z",
                "version": "1.0.0"
            }
        });
        
        let response = create_response(200, ResponseBody::Json(data.clone()));
        
        // Verify response structure
        assert_eq!(response.status_code, 200);
        assert_eq!(response.headers.get("Content-Type"), Some(&"application/json".to_string()));
        
        // Serialize and verify
        let serialized = serialize_response_body(&response.body);
        let deserialized: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
        
        assert_eq!(deserialized["success"], true);
        assert_eq!(deserialized["data"]["user"]["id"], 123);
        assert_eq!(deserialized["data"]["permissions"].as_array().unwrap().len(), 3);
    }
}
