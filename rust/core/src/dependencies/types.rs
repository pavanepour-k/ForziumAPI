use std::any::Any;
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum DependencyScope {
    Singleton,
    Request,
    Transient,
}

pub struct Dependency {
    pub key: String,
    pub scope: DependencyScope,
    pub factory: Box<dyn Fn() -> Box<dyn Any + Send + Sync> + Send + Sync>,
}

pub struct DependencyContext {
    pub singletons: HashMap<String, Box<dyn Any + Send + Sync>>,
    pub request_scoped: HashMap<String, Box<dyn Any + Send + Sync>>,
}
