use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct HttpRequest {
    pub method: crate::routing::HttpMethod,
    pub path: String,
    pub headers: HashMap<String, String>,
    pub query_params: HashMap<String, String>,
    pub body: RequestBody,
}

#[derive(Debug, Clone)]
pub enum RequestBody {
    Empty,
    Json(serde_json::Value),
    Form(HashMap<String, String>),
    Multipart(Vec<MultipartPart>),
    Raw(Vec<u8>),
}

#[derive(Debug, Clone)]
pub struct MultipartPart {
    pub name: String,
    pub filename: Option<String>,
    pub content_type: String,
    pub data: Vec<u8>,
}
