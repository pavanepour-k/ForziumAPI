use forzium::validation::{
    BufferValidator, Utf8Validator, NumericRangeValidator, SchemaValidator,
    JsonType, Validator,
};
use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PyTypeError};
use pyo3::types::{PyDict, PyList};
use serde_json::Value as JsonValue;

/// **PYTHON BUFFER VALIDATOR**
#[pyclass]
pub struct PyBufferValidator {
    inner: BufferValidator,
}

#[pymethods]
impl PyBufferValidator {
    /// **CONSTRUCTOR**
    #[new]
    #[pyo3(signature = (max_size=10485760, strict=false))]
    fn new(max_size: usize, strict: bool) -> Self {
        Self {
            inner: BufferValidator::with_strict(max_size, strict),
        }
    }

    /// **VALIDATE BUFFER**
    fn validate(&self, data: &[u8]) -> PyResult<()> {
        self.inner
            .validate(data.to_vec())
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

/// **PYTHON UTF-8 VALIDATOR**
#[pyclass]
pub struct PyUtf8Validator {
    inner: Utf8Validator,
}

#[pymethods]
impl PyUtf8Validator {
    /// **CONSTRUCTOR**
    #[new]
    #[pyo3(signature = (allow_empty=true, max_length=None))]
    fn new(allow_empty: bool, max_length: Option<usize>) -> Self {
        Self {
            inner: Utf8Validator::with_options(allow_empty, max_length),
        }
    }

    /// **VALIDATE UTF-8**
    fn validate(&self, data: &[u8]) -> PyResult<String> {
        self.inner
            .validate(data.to_vec())
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

/// **PYTHON NUMERIC VALIDATOR**
#[pyclass]
pub struct PyNumericValidator {
    min: f64,
    max: f64,
    type_name: String,
}

#[pymethods]
impl PyNumericValidator {
    /// **CONSTRUCTOR**
    #[new]
    #[pyo3(signature = (min, max, type_name="numeric"))]
    fn new(min: f64, max: f64, type_name: &str) -> Self {
        Self {
            min,
            max,
            type_name: type_name.to_string(),
        }
    }

    /// **VALIDATE NUMBER**
    fn validate(&self, value: f64) -> PyResult<f64> {
        if value >= self.min && value <= self.max {
            Ok(value)
        } else {
            Err(PyValueError::new_err(format!(
                "Value {} outside valid {} range {}..={}",
                value, self.type_name, self.min, self.max
            )))
        }
    }

    /// **VALIDATE INTEGER**
    fn validate_int(&self, value: i64) -> PyResult<i64> {
        let f_value = value as f64;
        if f_value >= self.min && f_value <= self.max {
            Ok(value)
        } else {
            Err(PyValueError::new_err(format!(
                "Value {} outside valid {} range {}..={}",
                value, self.type_name, self.min as i64, self.max as i64
            )))
        }
    }
}

/// **PYTHON SCHEMA VALIDATOR**
#[pyclass]
pub struct PySchemaValidator {
    inner: SchemaValidator,
}

#[pymethods]
impl PySchemaValidator {
    /// **CONSTRUCTOR**
    #[new]
    #[pyo3(signature = (strict=false))]
    fn new(strict: bool) -> Self {
        let validator = if strict {
            SchemaValidator::new().strict()
        } else {
            SchemaValidator::new()
        };
        
        Self { inner: validator }
    }

    /// **ADD REQUIRED FIELD**
    fn require_field(&mut self, field: &str, field_type: &str) -> PyResult<()> {
        let json_type = parse_json_type(field_type)?;
        self.inner = self.inner.clone().require_field(field, json_type);
        Ok(())
    }

    /// **ADD OPTIONAL FIELD**
    fn optional_field(&mut self, field: &str, field_type: &str) -> PyResult<()> {
        let json_type = parse_json_type(field_type)?;
        self.inner = self.inner.clone().optional_field(field, json_type);
        Ok(())
    }

    /// **VALIDATE JSON DATA**
    fn validate(&self, py: Python<'_>, data: &PyDict) -> PyResult<PyObject> {
        // Convert PyDict to serde_json::Value
        let json_value = py_dict_to_json(py, data)?;
        
        // Validate
        let result = self.inner
            .validate(json_value)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        
        // Convert back to Python
        json_to_py(py, &result)
    }
}

/// **HELPER FUNCTIONS**

/// **PARSE JSON TYPE STRING**
fn parse_json_type(type_str: &str) -> PyResult<JsonType> {
    match type_str.to_lowercase().as_str() {
        "string" | "str" => Ok(JsonType::String),
        "number" | "int" | "float" => Ok(JsonType::Number),
        "boolean" | "bool" => Ok(JsonType::Boolean),
        "array" | "list" => Ok(JsonType::Array),
        "object" | "dict" => Ok(JsonType::Object),
        "null" | "none" => Ok(JsonType::Null),
        _ => Err(PyTypeError::new_err(format!("Unknown type: {}", type_str))),
    }
}

/// **CONVERT PYTHON DICT TO JSON VALUE**
fn py_dict_to_json(py: Python<'_>, dict: &PyDict) -> PyResult<JsonValue> {
    let json_str = py.import("json")?.call_method1("dumps", (dict,))?;
    let json_string: String = json_str.extract()?;
    
    serde_json::from_str(&json_string)
        .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))
}

/// **CONVERT JSON VALUE TO PYTHON OBJECT**
fn json_to_py(py: Python<'_>, value: &JsonValue) -> PyResult<PyObject> {
    match value {
        JsonValue::Null => Ok(py.None()),
        JsonValue::Bool(b) => Ok(b.to_object(py)),
        JsonValue::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.to_object(py))
            } else if let Some(f) = n.as_f64() {
                Ok(f.to_object(py))
            } else {
                Ok(py.None())
            }
        }
        JsonValue::String(s) => Ok(s.to_object(py)),
        JsonValue::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.to_object(py))
        }
        JsonValue::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, json_to_py(py, v)?)?;
            }
            Ok(dict.to_object(py))
        }
    }
}

/// **CREATE U8 VALIDATOR**
#[pyfunction]
fn u8_validator() -> PyNumericValidator {
    PyNumericValidator::new(0.0, 255.0, "u8")
}

/// **CREATE I32 VALIDATOR**
#[pyfunction]
#[pyo3(signature = (min, max))]
fn i32_validator(min: i32, max: i32) -> PyNumericValidator {
    PyNumericValidator::new(min as f64, max as f64, "i32")
}

/// **CREATE F64 VALIDATOR**
#[pyfunction]
#[pyo3(signature = (min, max))]
fn f64_validator(min: f64, max: f64) -> PyNumericValidator {
    PyNumericValidator::new(min, max, "f64")
}

/// **VALIDATE JSON SCHEMA**
#[pyfunction]
#[pyo3(signature = (data, schema, /))]
fn validate_json_schema(py: Python<'_>, data: &PyDict, schema: &PyDict) -> PyResult<PyObject> {
    // Build validator from schema
    let mut validator = PySchemaValidator::new(false);
    
    // Process required fields
    if let Ok(required) = schema.get_item("required") {
        if let Ok(fields) = required.extract::<Vec<String>>() {
            for field in fields {
                if let Ok(field_type) = schema.get_item("properties")
                    .and_then(|props| props.get_item(&field))
                    .and_then(|prop| prop.get_item("type"))
                    .and_then(|t| t.extract::<String>()) 
                {
                    validator.require_field(&field, &field_type)?;
                }
            }
        }
    }
    
    validator.validate(py, data)
}

/// **REGISTER MODULE WITH PARENT**
pub fn register_module(parent: &PyModule) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "validation")?;
    
    // Add validator classes
    m.add_class::<PyBufferValidator>()?;
    m.add_class::<PyUtf8Validator>()?;
    m.add_class::<PyNumericValidator>()?;
    m.add_class::<PySchemaValidator>()?;
    
    // Add factory functions
    m.add_function(wrap_pyfunction!(u8_validator, m)?)?;
    m.add_function(wrap_pyfunction!(i32_validator, m)?)?;
    m.add_function(wrap_pyfunction!(f64_validator, m)?)?;
    m.add_function(wrap_pyfunction!(validate_json_schema, m)?)?;
    
    parent.add_submodule(m)?;
    Ok(())
}
