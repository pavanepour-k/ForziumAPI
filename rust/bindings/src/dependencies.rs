use forzium::dependencies::{Dependency, DependencyResolver, DependencyScope};
use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use std::any::Any;
use std::sync::{Arc, Mutex};
use std::collections::HashMap;

/// **PYTHON DEPENDENCY RESOLVER**
///
/// **PURPOSE**: Bridge Rust dependency injection to Python
/// **GUARANTEE**: Thread-safe dependency resolution across FFI boundary
#[pyclass]
pub struct PyDependencyResolver {
    inner: Arc<Mutex<DependencyResolver>>,
    python_factories: Arc<Mutex<HashMap<String, PyObject>>>,
}

#[pymethods]
impl PyDependencyResolver {
    /// **CONSTRUCTOR**
    #[new]
    fn new() -> Self {
        Self {
            inner: Arc::new(Mutex::new(DependencyResolver::new())),
            python_factories: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// **REGISTER DEPENDENCY**
    ///
    /// **PARAMETERS**:
    /// - `key: &str` - Unique dependency identifier
    /// - `factory: PyObject` - Python callable that creates the dependency
    /// - `scope: &str` - Lifecycle scope (singleton/request/transient)
    fn register(&mut self, key: &str, factory: PyObject, scope: &str) -> PyResult<()> {
        let dep_scope = match scope.to_lowercase().as_str() {
            "singleton" => DependencyScope::Singleton,
            "request" => DependencyScope::Request,
            "transient" => DependencyScope::Transient,
            _ => return Err(PyValueError::new_err(format!("Invalid scope: {}", scope))),
        };

        // Store Python factory
        self.python_factories
            .lock()
            .unwrap()
            .insert(key.to_string(), factory.clone());

        // Create Rust dependency with bridge to Python
        let key_clone = key.to_string();
        let factories = self.python_factories.clone();
        
        let dependency = Dependency {
            key: key.to_string(),
            scope: dep_scope,
            factory: Box::new(move || {
                Python::with_gil(|py| {
                    let factories_lock = factories.lock().unwrap();
                    if let Some(py_factory) = factories_lock.get(&key_clone) {
                        // Call Python factory and box the result
                        match py_factory.call0(py) {
                            Ok(result) => Box::new(result) as Box<dyn Any + Send + Sync>,
                            Err(_) => Box::new(()) as Box<dyn Any + Send + Sync>,
                        }
                    } else {
                        Box::new(()) as Box<dyn Any + Send + Sync>
                    }
                })
            }),
        };

        self.inner.lock().unwrap().register(dependency);
        Ok(())
    }

    /// **RESOLVE DEPENDENCY**
    ///
    /// **PARAMETERS**:
    /// - `key: &str` - Dependency identifier to resolve
    ///
    /// **RETURNS**: Resolved dependency instance
    fn resolve(&mut self, py: Python<'_>, key: &str) -> PyResult<PyObject> {
        let result = self.inner
            .lock()
            .unwrap()
            .resolve(key)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;

        // Extract PyObject from the Any type
        if let Some(py_obj) = result.downcast_ref::<PyObject>() {
            Ok(py_obj.clone())
        } else {
            // Fallback - return None if we can't extract the PyObject
            Ok(py.None())
        }
    }

    /// **CLEAR REQUEST SCOPE**
    ///
    /// **PURPOSE**: Release all request-scoped dependencies
    fn clear_request_scope(&mut self) -> PyResult<()> {
        self.inner.lock().unwrap().clear_request_scope();
        Ok(())
    }

    /// **GET REGISTERED DEPENDENCIES**
    ///
    /// **RETURNS**: List of registered dependency keys
    fn get_registered_keys(&self) -> Vec<String> {
        self.python_factories
            .lock()
            .unwrap()
            .keys()
            .cloned()
            .collect()
    }
}

/// **REGISTER MODULE WITH PARENT**
pub fn register_module(parent: &PyModule) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "dependencies")?;
    m.add_class::<PyDependencyResolver>()?;
    parent.add_submodule(m)?;
    Ok(())
}
