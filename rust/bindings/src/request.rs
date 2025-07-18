use forzium::request::{parse_form_body, parse_json_body, parse_query_string};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

#[pyfunction]
#[pyo3(signature = (query, /))]
fn parse_query_params(query: &str) -> HashMap<String, String> {
    parse_query_string(query)
}

#[pyfunction]
#[pyo3(signature = (data, /))]
fn parse_json(data: &[u8]) -> PyResult<PyObject> {
    Python::with_gil(|py| {
        let value = parse_json_body(data)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

        json_to_py(py, &value)
    })
}

#[pyfunction]
#[pyo3(signature = (data, /))]
fn parse_form(data: &[u8]) -> PyResult<HashMap<String, String>> {
    parse_form_body(data)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
}

fn json_to_py(py: Python, value: &serde_json::Value) -> PyResult<PyObject> {
    match value {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(b) => Ok(b.to_object(py)),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.to_object(py))
            } else if let Some(f) = n.as_f64() {
                Ok(f.to_object(py))
            } else {
                Ok(py.None())
            }
        }
        serde_json::Value::String(s) => Ok(s.to_object(py)),
        serde_json::Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.to_object(py))
        }
        serde_json::Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, json_to_py(py, v)?)?;
            }
            Ok(dict.to_object(py))
        }
    }
}

pub fn register_module(parent: &PyModule) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "request")?;
    m.add_function(wrap_pyfunction!(parse_query_params, m)?)?;
    m.add_function(wrap_pyfunction!(parse_json, m)?)?;
    m.add_function(wrap_pyfunction!(parse_form, m)?)?;
    parent.add_submodule(m)?;
    Ok(())
}
