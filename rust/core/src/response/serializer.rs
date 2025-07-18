use crate::response::types::{HttpResponse, ResponseBody};
use std::collections::HashMap;

pub fn serialize_json_response(value: &serde_json::Value) -> Vec<u8> {
    serde_json::to_vec(value).unwrap_or_default()
}

pub fn create_response(status: u16, body: ResponseBody) -> HttpResponse {
    let mut headers = HashMap::new();

    match &body {
        ResponseBody::Json(_) => {
            headers.insert("Content-Type".to_string(), "application/json".to_string());
        }
        ResponseBody::Text(_) => {
            headers.insert("Content-Type".to_string(), "text/plain".to_string());
        }
        ResponseBody::Binary(_) => {
            headers.insert(
                "Content-Type".to_string(),
                "application/octet-stream".to_string(),
            );
        }
        ResponseBody::Empty => {}
    }

    HttpResponse {
        status_code: status,
        headers,
        body,
    }
}

pub fn serialize_response_body(body: &ResponseBody) -> Vec<u8> {
    match body {
        ResponseBody::Empty => vec![],
        ResponseBody::Json(value) => serialize_json_response(value),
        ResponseBody::Text(text) => text.as_bytes().to_vec(),
        ResponseBody::Binary(data) => data.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_create_json_response() {
        let body = ResponseBody::Json(json!({"status": "ok"}));
        let response = create_response(200, body);

        assert_eq!(response.status_code, 200);
        assert_eq!(
            response.headers.get("Content-Type"),
            Some(&"application/json".to_string())
        );
    }

    #[test]
    fn test_serialize_json() {
        let value = json!({"test": "data"});
        let serialized = serialize_json_response(&value);
        assert!(!serialized.is_empty());
    }
}
