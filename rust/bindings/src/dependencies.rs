use forzium::dependencies::{Dependency, DependencyResolver, DependencyScope};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::any::Any;
use std::collections::HashMap;
use std::panic;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex, RwLock};

// Object counter for tracking
static RESOLVER_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Catch panics for dependency operations
fn catch_panic_deps<F, R>(f: F) -> PyResult<R>
where
    F: FnOnce() -> PyResult<R> + panic::UnwindSafe,
{
    match panic::catch_unwind(f) {
        Ok(result) => result,
        Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
            "Rust panic occurred in dependencies module",
        )),
    }
}

/// **PYTHON DEPENDENCY RESOLVER**
///
/// **PURPOSE**: Bridge Rust dependency injection to Python
/// **GUARANTEE**: Thread-safe dependency resolution across FFI boundary
#[pyclass]
pub struct PyDependencyResolver {
    // Use Arc for shared ownership across FFI boundary
    inner: Arc<Mutex<DependencyResolver>>,
    // Use RwLock for read-heavy Python factory access
    python_factories: Arc<RwLock<HashMap<String, PyObject>>>,
    #[pyo3(get)]
    id: u64, // Unique ID for lifetime tracking
}

#[pymethods]
impl PyDependencyResolver {
    /// **CONSTRUCTOR**
    #[new]
    fn new() -> Self {
        let id = RESOLVER_COUNTER.fetch_add(1, Ordering::SeqCst);

        #[cfg(debug_assertions)]
        log::debug!("Creating PyDependencyResolver {}", id);

        Self {
            inner: Arc::new(Mutex::new(DependencyResolver::new())),
            python_factories: Arc::new(RwLock::new(HashMap::new())),
            id,
        }
    }

    /// **REGISTER DEPENDENCY**
    ///
    /// **PARAMETERS**:
    /// - `key: &str` - Unique dependency identifier
    /// - `factory: PyObject` - Python callable that creates the dependency
    /// - `scope: &str` - Lifecycle scope (singleton/request/transient)
    fn register(&mut self, key: &str, factory: PyObject, scope: &str) -> PyResult<()> {
        catch_panic_deps(|| {
            // Validate inputs
            if key.is_empty() {
                return Err(PyValueError::new_err("Dependency key cannot be empty"));
            }

            if key.len() > 256 {
                // Max key length
                return Err(PyValueError::new_err(
                    "Dependency key exceeds maximum length (256)",
                ));
            }

            let dep_scope = match scope.to_lowercase().as_str() {
                "singleton" => DependencyScope::Singleton,
                "request" => DependencyScope::Request,
                "transient" => DependencyScope::Transient,
                _ => return Err(PyValueError::new_err(format!("Invalid scope: {}", scope))),
            };

            #[cfg(debug_assertions)]
            log::debug!(
                "PyDependencyResolver {}: Registering {} with scope {:?}",
                self.id,
                key,
                dep_scope
            );

            // Store Python factory with write lock
            {
                let mut factories = self
                    .python_factories
                    .write()
                    .map_err(|_| PyValueError::new_err("Failed to acquire write lock"))?;
                factories.insert(key.to_string(), factory.clone());
            }

            // Create Rust dependency with bridge to Python
            let key_clone = key.to_string();
            let factories = Arc::clone(&self.python_factories);

            let dependency = Dependency {
                key: key.to_string(),
                scope: dep_scope,
                factory: Box::new(move || {
                    Python::with_gil(|py| {
                        // Use read lock for factory access
                        let factories_guard = factories.read().unwrap();
                        if let Some(py_factory) = factories_guard.get(&key_clone) {
                            // Call Python factory and box the result
                            match py_factory.call0(py) {
                                Ok(result) => Box::new(result) as Box<dyn Any + Send + Sync>,
                                Err(e) => {
                                    log::error!(
                                        "Failed to create dependency '{}': {}",
                                        key_clone,
                                        e
                                    );
                                    Box::new(()) as Box<dyn Any + Send + Sync>
                                }
                            }
                        } else {
                            log::error!("Factory not found for dependency '{}'", key_clone);
                            Box::new(()) as Box<dyn Any + Send + Sync>
                        }
                    })
                }),
            };

            // Register with mutex protection
            let mut resolver = self
                .inner
                .lock()
                .map_err(|_| PyValueError::new_err("Failed to acquire resolver lock"))?;
            resolver.register(dependency);

            Ok(())
        })
    }

    /// **RESOLVE DEPENDENCY**
    ///
    /// **PARAMETERS**:
    /// - `key: &str` - Dependency identifier to resolve
    ///
    /// **RETURNS**: Resolved dependency instance
    fn resolve(&mut self, py: Python<'_>, key: &str) -> PyResult<PyObject> {
        catch_panic_deps(|| {
            // Validate input
            if key.is_empty() {
                return Err(PyValueError::new_err("Dependency key cannot be empty"));
            }

            #[cfg(debug_assertions)]
            log::debug!("PyDependencyResolver {}: Resolving {}", self.id, key);

            let result = {
                let mut resolver = self
                    .inner
                    .lock()
                    .map_err(|_| PyValueError::new_err("Failed to acquire resolver lock"))?;
                resolver
                    .resolve(key)
                    .map_err(|e| PyValueError::new_err(e.to_string()))?
            };

            // Extract PyObject from the Any type
            if let Some(py_obj) = result.downcast_ref::<PyObject>() {
                Ok(py_obj.clone())
            } else {
                // Fallback - return None if we can't extract the PyObject
                log::warn!("Failed to extract PyObject for dependency '{}'", key);
                Ok(py.None())
            }
        })
    }

    /// **CLEAR REQUEST SCOPE**
    ///
    /// **PURPOSE**: Release all request-scoped dependencies
    fn clear_request_scope(&mut self) -> PyResult<()> {
        catch_panic_deps(|| {
            #[cfg(debug_assertions)]
            log::debug!("PyDependencyResolver {}: Clearing request scope", self.id);

            let mut resolver = self
                .inner
                .lock()
                .map_err(|_| PyValueError::new_err("Failed to acquire resolver lock"))?;
            resolver.clear_request_scope();
            Ok(())
        })
    }

    /// **GET REGISTERED DEPENDENCIES**
    ///
    /// **RETURNS**: List of registered dependency keys
    fn get_registered_keys(&self) -> PyResult<Vec<String>> {
        catch_panic_deps(|| {
            let factories = self
                .python_factories
                .read()
                .map_err(|_| PyValueError::new_err("Failed to acquire read lock"))?;
            Ok(factories.keys().cloned().collect())
        })
    }

    /// **GET DEPENDENCY COUNT**
    fn dependency_count(&self) -> PyResult<usize> {
        catch_panic_deps(|| {
            let factories = self
                .python_factories
                .read()
                .map_err(|_| PyValueError::new_err("Failed to acquire read lock"))?;
            Ok(factories.len())
        })
    }

    /// String representation for debugging
    fn __repr__(&self) -> PyResult<String> {
        let count = self.dependency_count()?;
        Ok(format!(
            "PyDependencyResolver(id={}, dependencies={})",
            self.id, count
        ))
    }
}

/// Implement Drop to track object lifecycle
impl Drop for PyDependencyResolver {
    fn drop(&mut self) {
        #[cfg(debug_assertions)]
        {
            let count = self.python_factories.read().map(|f| f.len()).unwrap_or(0);
            log::debug!(
                "Dropping PyDependencyResolver {} with {} dependencies",
                self.id,
                count
            );
        }
    }
}

/// **REGISTER MODULE WITH PARENT**
pub fn register_module(parent: &PyModule) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "dependencies")?;
    m.add_class::<PyDependencyResolver>()?;
    parent.add_submodule(m)?;
    Ok(())
}
