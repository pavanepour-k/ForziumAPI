use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct HttpResponse {
    pub status_code: u16,
    pub headers: HashMap<String, String>,
    pub body: ResponseBody,
}

#[derive(Debug, Clone)]
pub enum ResponseBody {
    Empty,
    Json(serde_json::Value),
    Text(String),
    Binary(Vec<u8>),
}
