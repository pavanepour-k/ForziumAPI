use forzium::response::{
    create_response, serialize_json_response, serialize_response_body, HttpResponse, ResponseBody,
};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::collections::HashMap;
use std::panic;
use std::sync::atomic::{AtomicU64, Ordering};

// Object counter for tracking
static RESPONSE_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Catch panics for response operations
fn catch_panic_response<F, R>(f: F) -> PyResult<R>
where
    F: FnOnce() -> PyResult<R> + panic::UnwindSafe,
{
    match panic::catch_unwind(f) {
        Ok(result) => result,
        Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
            "Rust panic occurred in response module",
        )),
    }
}

/// **PYTHON RESPONSE BUILDER**
///
/// **PURPOSE**: Create HTTP responses with Rust performance
/// **GUARANTEE**: Efficient serialization across FFI boundary
#[pyclass]
pub struct PyResponseBuilder {
    status_code: u16,
    headers: HashMap<String, String>,
    body: Option<ResponseBody>,
    #[pyo3(get)]
    id: u64,
}

#[pymethods]
impl PyResponseBuilder {
    /// **CONSTRUCTOR**
    #[new]
    fn new() -> Self {
        let id = RESPONSE_COUNTER.fetch_add(1, Ordering::SeqCst);

        #[cfg(debug_assertions)]
        log::debug!("Creating PyResponseBuilder {}", id);

        Self {
            status_code: 200,
            headers: HashMap::new(),
            body: None,
            id,
        }
    }

    /// **SET STATUS CODE**
    fn status(&mut self, code: u16) -> PyResult<()> {
        catch_panic_response(|| {
            if !(100..=599).contains(&code) {
                return Err(PyValueError::new_err(format!(
                    "Invalid HTTP status code: {}",
                    code
                )));
            }
            self.status_code = code;
            Ok(())
        })
    }

    /// **ADD HEADER**
    fn header(&mut self, key: &str, value: &str) -> PyResult<()> {
        catch_panic_response(|| {
            // Validate header name
            if key.is_empty() || key.len() > 256 {
                return Err(PyValueError::new_err("Invalid header name"));
            }

            // Validate header value
            if value.len() > 8192 {
                // Common header size limit
                return Err(PyValueError::new_err("Header value too large"));
            }

            self.headers.insert(key.to_string(), value.to_string());
            Ok(())
        })
    }

    /// **SET JSON BODY**
    fn json_body(&mut self, py: Python<'_>, data: &PyDict) -> PyResult<()> {
        catch_panic_response(|| {
            // Size check
            let json_str = py.import("json")?.call_method1("dumps", (data,))?;
            let json_string: String = json_str.extract()?;

            if json_string.len() > 10_485_760 {
                // 10MB limit
                return Err(PyValueError::new_err("JSON body exceeds 10MB limit"));
            }

            let json_value: serde_json::Value = serde_json::from_str(&json_string)
                .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))?;

            self.body = Some(ResponseBody::Json(json_value));
            Ok(())
        })
    }

    /// **SET TEXT BODY**
    fn text_body(&mut self, text: &str) -> PyResult<()> {
        catch_panic_response(|| {
            if text.len() > 10_485_760 {
                // 10MB limit
                return Err(PyValueError::new_err("Text body exceeds 10MB limit"));
            }

            self.body = Some(ResponseBody::Text(text.to_string()));
            Ok(())
        })
    }

    /// **SET BINARY BODY**
    fn binary_body(&mut self, data: &[u8]) -> PyResult<()> {
        catch_panic_response(|| {
            if data.len() > 10_485_760 {
                // 10MB limit
                return Err(PyValueError::new_err("Binary body exceeds 10MB limit"));
            }

            self.body = Some(ResponseBody::Binary(data.to_vec()));
            Ok(())
        })
    }

    /// **BUILD RESPONSE**
    fn build(&self) -> PyResult<PyHttpResponse> {
        catch_panic_response(|| {
            let body = self.body.clone().unwrap_or(ResponseBody::Empty);
            let response = create_response(self.status_code, body);

            Ok(PyHttpResponse {
                inner: response,
                id: RESPONSE_COUNTER.fetch_add(1, Ordering::SeqCst),
            })
        })
    }

    /// String representation for debugging
    fn __repr__(&self) -> String {
        format!(
            "PyResponseBuilder(id={}, status={}, headers={})",
            self.id,
            self.status_code,
            self.headers.len()
        )
    }
}

impl Drop for PyResponseBuilder {
    fn drop(&mut self) {
        #[cfg(debug_assertions)]
        log::debug!("Dropping PyResponseBuilder {}", self.id);
    }
}

/// **PYTHON HTTP RESPONSE**
///
/// **PURPOSE**: Wrap Rust HttpResponse for Python consumption
#[pyclass]
pub struct PyHttpResponse {
    inner: HttpResponse,
    #[pyo3(get)]
    id: u64,
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
    fn body_bytes(&self, py: Python<'_>) -> PyResult<PyObject> {
        catch_panic_response(|| {
            let bytes = serialize_response_body(&self.inner.body);
            Ok(PyBytes::new(py, &bytes).into())
        })
    }

    /// **GET BODY AS STRING**
    fn body_string(&self) -> PyResult<String> {
        catch_panic_response(|| match &self.inner.body {
            ResponseBody::Text(text) => Ok(text.clone()),
            ResponseBody::Json(value) => Ok(value.to_string()),
            ResponseBody::Empty => Ok(String::new()),
            ResponseBody::Binary(data) => String::from_utf8(data.clone()).map_err(|e| {
                PyValueError::new_err(format!("Binary data is not valid UTF-8: {}", e))
            }),
        })
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

    /// String representation for debugging
    fn __repr__(&self) -> String {
        let body_type = match &self.inner.body {
            ResponseBody::Json(_) => "JSON",
            ResponseBody::Text(_) => "Text",
            ResponseBody::Binary(_) => "Binary",
            ResponseBody::Empty => "Empty",
        };
        format!(
            "PyHttpResponse(id={}, status={}, body_type={})",
            self.id, self.inner.status_code, body_type
        )
    }
}

impl Drop for PyHttpResponse {
    fn drop(&mut self) {
        #[cfg(debug_assertions)]
        log::debug!("Dropping PyHttpResponse {}", self.id);
    }
}

/// **HELPER FUNCTIONS**

/// **SERIALIZE JSON TO BYTES**
#[pyfunction]
#[pyo3(signature = (data, /))]
fn serialize_json(py: Python<'_>, data: &PyDict) -> PyResult<PyObject> {
    catch_panic_response(|| {
        // Convert PyDict to JSON string
        let json_str = py.import("json")?.call_method1("dumps", (data,))?;
        let json_string: String = json_str.extract()?;

        if json_string.len() > 10_485_760 {
            // 10MB limit
            return Err(PyValueError::new_err("JSON exceeds 10MB limit"));
        }

        // Parse and serialize
        let json_value: serde_json::Value = serde_json::from_str(&json_string)
            .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))?;

        let bytes = serialize_json_response(&json_value);
        Ok(PyBytes::new(py, &bytes).into())
    })
}

/// **CREATE JSON RESPONSE**
#[pyfunction]
#[pyo3(signature = (status, data, /))]
fn json_response(py: Python<'_>, status: u16, data: &PyDict) -> PyResult<PyHttpResponse> {
    catch_panic_response(|| {
        let mut builder = PyResponseBuilder::new();
        builder.status(status)?;
        builder.json_body(py, data)?;
        builder.build()
    })
}

/// **CREATE TEXT RESPONSE**
#[pyfunction]
#[pyo3(signature = (status, text, /))]
fn text_response(status: u16, text: &str) -> PyResult<PyHttpResponse> {
    catch_panic_response(|| {
        let mut builder = PyResponseBuilder::new();
        builder.status(status)?;
        builder.text_body(text)?;
        builder.build()
    })
}

/// **CREATE BINARY RESPONSE**
#[pyfunction]
#[pyo3(signature = (status, data, /))]
fn binary_response(status: u16, data: &[u8]) -> PyResult<PyHttpResponse> {
    catch_panic_response(|| {
        let mut builder = PyResponseBuilder::new();
        builder.status(status)?;
        builder.binary_body(data)?;
        builder.build()
    })
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
