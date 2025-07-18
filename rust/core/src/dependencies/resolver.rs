use crate::dependencies::types::{Dependency, DependencyContext, DependencyScope};
use crate::errors::ProjectError;
use std::any::Any;
use std::collections::HashMap;
use std::sync::Arc;

/// **DEPENDENCY RESOLVER**
///
/// **MANDATE**: Thread-safe dependency injection with lifecycle management
/// **GUARANTEE**: Memory-efficient resolution with proper scoping
pub struct DependencyResolver {
    dependencies: HashMap<String, Dependency>,
    context: DependencyContext,
}

impl DependencyResolver {
    /// **CONSTRUCTOR**
    pub fn new() -> Self {
        Self {
            dependencies: HashMap::new(),
            context: DependencyContext {
                singletons: HashMap::new(),
                request_scoped: HashMap::new(),
            },
        }
    }

    /// **DEPENDENCY REGISTRATION**
    ///
    /// **PARAMETERS**:
    /// - `dependency: Dependency` - Configured dependency instance
    pub fn register(&mut self, dependency: Dependency) {
        self.dependencies.insert(dependency.key.clone(), dependency);
    }

    /// **DEPENDENCY RESOLUTION**
    ///
    /// **PARAMETERS**:
    /// - `key: &str` - Dependency identifier
    ///
    /// **RETURNS**:
    /// - `Ok(Box<dyn Any + Send + Sync>)` - Resolved dependency instance
    /// - `Err(ProjectError)` - Resolution failure
    pub fn resolve(&mut self, key: &str) -> Result<Arc<Box<dyn Any + Send + Sync>>, ProjectError> {
        let dep = self
            .dependencies
            .get(key)
            .ok_or_else(|| ProjectError::Validation {
                code: "RUST_CORE_VALIDATION_DEPENDENCY_NOT_FOUND".to_string(),
                message: format!("Dependency '{}' not registered", key),
            })?;

        match dep.scope {
            DependencyScope::Singleton => {
                if !self.context.singletons.contains_key(key) {
                    let instance = (dep.factory)();
                    self.context.singletons.insert(key.to_string(), Arc::new(instance));
                }
                Ok(self.context.singletons.get(key).unwrap().clone())
            }
            DependencyScope::Request => {
                if !self.context.request_scoped.contains_key(key) {
                    let instance = (dep.factory)();
                    self.context
                        .request_scoped
                        .insert(key.to_string(), Arc::new(instance));
                }
                Ok(self.context.request_scoped.get(key).unwrap().clone())
            }
            DependencyScope::Transient => Ok(Arc::new((dep.factory)())),
        }
    }

    /// **CLEAR REQUEST SCOPE**
    ///
    /// **PURPOSE**: Release request-scoped instances for memory management
    pub fn clear_request_scope(&mut self) {
        self.context.request_scoped.clear();
    }
}

impl Default for DependencyResolver {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dependencies::types::DependencyScope;

    #[test]
    fn test_dependency_resolver_registration() {
        let mut resolver = DependencyResolver::new();
        
        let dep = Dependency {
            key: "test_service".to_string(),
            scope: DependencyScope::Singleton,
            factory: Box::new(|| Box::new("test_value".to_string())),
        };
        
        resolver.register(dep);
        assert!(resolver.dependencies.contains_key("test_service"));
    }

    #[test]
    fn test_singleton_resolution() {
        let mut resolver = DependencyResolver::new();
        
        let dep = Dependency {
            key: "singleton_service".to_string(),
            scope: DependencyScope::Singleton,
            factory: Box::new(|| Box::new(42i32)),
        };
        
        resolver.register(dep);
        
        let instance1 = resolver.resolve("singleton_service").unwrap();
        let instance2 = resolver.resolve("singleton_service").unwrap();
        
        // **VERIFY**: Same instance returned for singleton
        assert!(Arc::ptr_eq(&instance1, &instance2));
    }

    #[test]
    fn test_transient_resolution() {
        let mut resolver = DependencyResolver::new();
        
        let dep = Dependency {
            key: "transient_service".to_string(),
            scope: DependencyScope::Transient,
            factory: Box::new(|| Box::new(42i32)),
        };
        
        resolver.register(dep);
        
        let instance1 = resolver.resolve("transient_service").unwrap();
        let instance2 = resolver.resolve("transient_service").unwrap();
        
        // **VERIFY**: Different instances for transient
        assert!(!Arc::ptr_eq(&instance1, &instance2));
    }

    #[test]
    fn test_unregistered_dependency_error() {
        let mut resolver = DependencyResolver::new();
        let result = resolver.resolve("nonexistent");
        
        assert!(result.is_err());
        match result.unwrap_err() {
            ProjectError::Validation { code, .. } => {
                assert!(code.contains("DEPENDENCY_NOT_FOUND"));
            }
            _ => panic!("Expected validation error"),
        }
    }
}
