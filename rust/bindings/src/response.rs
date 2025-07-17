use forzium::response::{HttpResponse, ResponseBody, create_response, serialize_json_response, serialize_response_body};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyBytes};
use std::collections::HashMap;

/// **PYTHON RESPONSE BUILDER**
///
/// **PURPOSE**: Create HTTP responses with Rust performance
/// **GUARANTEE**: Efficient serialization across FFI boundary
#[pyclass]
pub struct PyResponseBuilder {
    status_code: u16,
    headers: HashMap<String, String>,
    body: Option<ResponseBody>,
}

#[pymethods]
impl PyResponseBuilder {
    /// **CONSTRUCTOR**
    #[new]
    fn new() -> Self {
        Self {
            status_code: 200,
            headers: HashMap::new(),
            body: None,
        }
    }

    /// **SET STATUS CODE**
    fn status(&mut self, code: u16) -> PyResult<()> {
        self.status_code = code;
        Ok(())
    }

    /// **ADD HEADER**
    fn header(&mut self, key: &str, value: &str) -> PyResult<()> {
        self.headers.insert(key.to_string(), value.to_string());
        Ok(())
    }

    /// **SET JSON BODY**
    fn json_body(&mut self, py: Python<'_>, data: &PyDict) -> PyResult<()> {
        // Convert PyDict to serde_json::Value
        let json_str = py.import("json")?.call_method1("dumps", (data,))?;
        let json_string: String = json_str.extract()?;
        let json_value: serde_json::Value = serde_json::from_str(&json_string)
            .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))?;
        
        self.body = Some(ResponseBody::Json(json_value));
        Ok(())
    }

    /// **SET TEXT BODY**
    fn text_body(&mut self, text: &str) -> PyResult<()> {
        self.body = Some(ResponseBody::Text(text.to_string()));
        Ok(())
    }

    /// **SET BINARY BODY**
    fn binary_body(&mut self, data: &[u8]) -> PyResult<()> {
        self.body = Some(ResponseBody::Binary(data.to_vec()));
        Ok(())
    }

    /// **BUILD RESPONSE**
    fn build(&self) -> PyResult<PyHttpResponse> {
        let body = self.body.clone().unwrap_or(ResponseBody::Empty);
        let response = create_response(self.status_code, body);
        
        Ok(PyHttpResponse { inner: response })
    }
}

/// **PYTHON HTTP RESPONSE**
///
/// **PURPOSE**: Wrap Rust HttpResponse for Python consumption
#[pyclass]
pub struct PyHttpResponse {
    inner: HttpResponse,
}

#[pymethods]
impl PyHttpResponse {
    /// **GET STATUS CODE**
    #[getter]
    fn status_code(&self) -> u16 {
        self.inner.status_code
    }

    /// **GET HEADERS**
    #[getter]
    fn headers(&self, py: Python<'_>) -> PyObject {
        let dict = PyDict::new(py);
        for (key, value) in &self.inner.headers {
            dict.set_item(key, value).unwrap();
        }
        dict.into()
    }

    /// **GET BODY AS BYTES**
    fn body_bytes(&self, py: Python<'_>) -> PyObject {
        let bytes = serialize_response_body(&self.inner.body);
        PyBytes::new(py, &bytes).into()
    }

    /// **GET BODY AS STRING**
    fn body_string(&self) -> PyResult<String> {
        match &self.inner.body {
            ResponseBody::Text(text) => Ok(text.clone()),
            ResponseBody::Json(value) => Ok(value.to_string()),
            ResponseBody::Empty => Ok(String::new()),
            ResponseBody::Binary(data) => {
                String::from_utf8(data.clone())
                    .map_err(|e| PyValueError::new_err(format!("Binary data is not valid UTF-8: {}", e)))
            }
        }
    }

    /// **IS JSON RESPONSE**
    fn is_json(&self) -> bool {
        matches!(self.inner.body, ResponseBody::Json(_))
    }

    /// **IS TEXT RESPONSE**
    fn is_text(&self) -> bool {
        matches!(self.inner.body, ResponseBody::Text(_))
    }

    /// **IS BINARY RESPONSE**
    fn is_binary(&self) -> bool {
        matches!(self.inner.body, ResponseBody::Binary(_))
    }

    /// **IS EMPTY RESPONSE**
    fn is_empty(&self) -> bool {
        matches!(self.inner.body, ResponseBody::Empty)
    }
}

/// **HELPER FUNCTIONS**

/// **SERIALIZE JSON TO BYTES**
#[pyfunction]
#[pyo3(signature = (data, /))]
fn serialize_json(py: Python<'_>, data: &PyDict) -> PyResult<PyObject> {
    // Convert PyDict to JSON string
    let json_str = py.import("json")?.call_method1("dumps", (data,))?;
    let json_string: String = json_str.extract()?;
    
    // Parse and serialize
    let json_value: serde_json::Value = serde_json::from_str(&json_string)
        .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))?;
    
    let bytes = serialize_json_response(&json_value);
    Ok(PyBytes::new(py, &bytes).into())
}

/// **CREATE JSON RESPONSE**
#[pyfunction]
#[pyo3(signature = (status, data, /))]
fn json_response(py: Python<'_>, status: u16, data: &PyDict) -> PyResult<PyHttpResponse> {
    let mut builder = PyResponseBuilder::new();
    builder.status(status)?;
    builder.json_body(py, data)?;
    builder.build()
}

/// **CREATE TEXT RESPONSE**
#[pyfunction]
#[pyo3(signature = (status, text, /))]
fn text_response(status: u16, text: &str) -> PyResult<PyHttpResponse> {
    let mut builder = PyResponseBuilder::new();
    builder.status(status)?;
    builder.text_body(text)?;
    builder.build()
}

/// **CREATE BINARY RESPONSE**
#[pyfunction]
#[pyo3(signature = (status, data, /))]
fn binary_response(status: u16, data: &[u8]) -> PyResult<PyHttpResponse> {
    let mut builder = PyResponseBuilder::new();
    builder.status(status)?;
    builder.binary_body(data)?;
    builder.build()
}

/// **REGISTER MODULE WITH PARENT**
pub fn register_module(parent: &PyModule) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "response")?;
    
    // Add classes
    m.add_class::<PyResponseBuilder>()?;
    m.add_class::<PyHttpResponse>()?;
    
    // Add functions
    m.add_function(wrap_pyfunction!(serialize_json, m)?)?;
    m.add_function(wrap_pyfunction!(json_response, m)?)?;
    m.add_function(wrap_pyfunction!(text_response, m)?)?;
    m.add_function(wrap_pyfunction!(binary_response, m)?)?;
    
    parent.add_submodule(m)?;
    Ok(())
}
