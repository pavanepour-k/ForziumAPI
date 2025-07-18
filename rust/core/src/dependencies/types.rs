use std::any::Any;
use std::collections::HashMap;
use std::sync::Arc;

/// **DEPENDENCY SCOPE ENUMERATION**
///
/// **MANDATE**: ALL dependency registrations MUST specify scope
/// **CRITICAL**: Scope determines instance lifecycle management
#[derive(Debug, Clone, PartialEq)]
pub enum DependencyScope {
    /// **SINGLETON** - Single instance per application lifecycle
    Singleton,
    /// **REQUEST** - Single instance per request lifecycle  
    Request,
    /// **TRANSIENT** - New instance per resolution
    Transient,
}

/// **DEPENDENCY REGISTRATION CONTAINER**
///
/// **PURPOSE**: Encapsulates dependency configuration and factory
/// **GUARANTEE**: Thread-safe dependency instantiation
pub struct Dependency {
    /// **UNIQUE IDENTIFIER** - Dependency resolution key
    pub key: String,
    /// **LIFECYCLE SCOPE** - Instance management strategy
    pub scope: DependencyScope,
    /// **FACTORY FUNCTION** - Instance creation mechanism
    pub factory: Box<dyn Fn() -> Box<dyn Any + Send + Sync> + Send + Sync>,
}

/// **DEPENDENCY CONTEXT STORAGE**
///
/// **PURPOSE**: Runtime storage for resolved instances
/// **CRITICAL**: Thread-safe instance caching with proper scoping
pub struct DependencyContext {
    /// **SINGLETON INSTANCES** - Application-lifetime cache
    pub singletons: HashMap<String, Arc<Box<dyn Any + Send + Sync>>>,
    /// **REQUEST INSTANCES** - Request-lifetime cache
    pub request_scoped: HashMap<String, Arc<Box<dyn Any + Send + Sync>>>,
}
