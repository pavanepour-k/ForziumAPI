use crate::dependencies::types::{Dependency, DependencyContext, DependencyScope};
use crate::errors::ProjectError;
use std::any::Any;
use std::collections::HashMap;

pub struct DependencyResolver {
    dependencies: HashMap<String, Dependency>,
    context: DependencyContext,
}

impl DependencyResolver {
    pub fn new() -> Self {
        Self {
            dependencies: HashMap::new(),
            context: DependencyContext {
                singletons: HashMap::new(),
                request_scoped: HashMap::new(),
            },
        }
    }

    pub fn register(&mut self, dependency: Dependency) {
        self.dependencies.insert(dependency.key.clone(), dependency);
    }

    pub fn resolve(&mut self, key: &str) -> Result<Box<dyn Any + Send + Sync>, ProjectError> {
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
                    self.context.singletons.insert(key.to_string(), instance);
                }
                Ok(self.context.singletons.get(key).unwrap().clone())
            }
            DependencyScope::Request => {
                if !self.context.request_scoped.contains_key(key) {
                    let instance = (dep.factory)();
                    self.context
                        .request_scoped
                        .insert(key.to_string(), instance);
                }
                Ok(self.context.request_scoped.get(key).unwrap().clone())
            }
            DependencyScope::Transient => Ok((dep.factory)()),
        }
    }

    pub fn clear_request_scope(&mut self) {
        self.context.request_scoped.clear();
    }
}

impl Default for DependencyResolver {
    fn default() -> Self {
        Self::new()
    }
}
