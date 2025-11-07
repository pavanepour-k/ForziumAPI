use once_cell::sync::Lazy;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::RwLock;

/// Global resource limits configuration for compute operations.
pub struct ResourceLimits {
    /// Maximum number of elements in a tensor (rows * cols).
    pub max_elements: AtomicUsize,
    /// Maximum number of concurrent compute operations.
    pub max_concurrent_ops: AtomicUsize,
    /// Current number of active compute operations.
    pub active_ops: AtomicUsize,
    /// Whether resource limits are enabled.
    pub enabled: AtomicUsize,
    /// Custom limits for specific operation types.
    pub operation_limits: RwLock<std::collections::HashMap<String, usize>>,
}

/// The global resource limits instance.
pub static RESOURCE_LIMITS: Lazy<ResourceLimits> = Lazy::new(|| {
    let mut operation_limits = std::collections::HashMap::new();
    // Set default operation-specific limits
    operation_limits.insert("matmul".to_string(), 100_000_000); // 10k x 10k matrix
    operation_limits.insert("conv2d".to_string(), 50_000_000); // More expensive operation

    ResourceLimits {
        max_elements: AtomicUsize::new(100_000_000), // 10k x 10k default
        max_concurrent_ops: AtomicUsize::new(16),    // Default to 16 concurrent ops
        active_ops: AtomicUsize::new(0),             // Start with 0 active ops
        enabled: AtomicUsize::new(1),                // Enabled by default
        operation_limits: RwLock::new(operation_limits),
    }
});

/// Reset resource limits to default values.
pub fn reset_defaults() {
    RESOURCE_LIMITS
        .max_elements
        .store(100_000_000, Ordering::SeqCst);
    RESOURCE_LIMITS
        .max_concurrent_ops
        .store(16, Ordering::SeqCst);
    RESOURCE_LIMITS.enabled.store(1, Ordering::SeqCst);

    let mut op_limits = RESOURCE_LIMITS.operation_limits.write().unwrap();
    op_limits.clear();
    op_limits.insert("matmul".to_string(), 100_000_000);
    op_limits.insert("conv2d".to_string(), 50_000_000);
}

/// Check if an operation with the given dimensions is allowed.
pub fn check_tensor_size(rows: usize, cols: usize, operation: &str) -> Result<(), String> {
    if RESOURCE_LIMITS.enabled.load(Ordering::SeqCst) == 0 {
        return Ok(()); // Limits disabled
    }

    let elements = rows * cols;
    let max_elements = RESOURCE_LIMITS.max_elements.load(Ordering::SeqCst);

    if elements > max_elements {
        return Err(format!(
            "Tensor size exceeds global limit: {} elements (limit: {})",
            elements, max_elements
        ));
    }

    // Check operation-specific limits if they exist
    let op_limits = RESOURCE_LIMITS.operation_limits.read().unwrap();
    if let Some(&limit) = op_limits.get(operation) {
        if elements > limit {
            return Err(format!(
                "Tensor size exceeds limit for operation '{}': {} elements (limit: {})",
                operation, elements, limit
            ));
        }
    }

    Ok(())
}

/// Resource guard that tracks active operations.
pub struct OpGuard;

impl OpGuard {
    /// Try to acquire a resource guard for a new compute operation.
    /// Returns None if the maximum concurrent operations limit is reached.
    pub fn try_new() -> Option<Self> {
        if RESOURCE_LIMITS.enabled.load(Ordering::SeqCst) == 0 {
            return Some(OpGuard); // Limits disabled
        }

        let active = RESOURCE_LIMITS.active_ops.fetch_add(1, Ordering::SeqCst);
        let max = RESOURCE_LIMITS.max_concurrent_ops.load(Ordering::SeqCst);

        if active >= max {
            // Undo the increment and return None
            RESOURCE_LIMITS.active_ops.fetch_sub(1, Ordering::SeqCst);
            None
        } else {
            Some(OpGuard)
        }
    }
}

impl Drop for OpGuard {
    fn drop(&mut self) {
        if RESOURCE_LIMITS.enabled.load(Ordering::SeqCst) != 0 {
            RESOURCE_LIMITS.active_ops.fetch_sub(1, Ordering::SeqCst);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resource_limit_check() {
        assert!(check_tensor_size(1000, 1000, "matmul").is_ok());
        assert!(check_tensor_size(100000, 100000, "matmul").is_err());
    }

    #[test]
    fn test_op_guard() {
        // Enable resource limits
        RESOURCE_LIMITS.enabled.store(1, Ordering::SeqCst);
        RESOURCE_LIMITS
            .max_concurrent_ops
            .store(3, Ordering::SeqCst);
        RESOURCE_LIMITS.active_ops.store(0, Ordering::SeqCst);

        let guard1 = OpGuard::try_new();
        let guard2 = OpGuard::try_new();
        let guard3 = OpGuard::try_new();
        let guard4 = OpGuard::try_new();

        assert!(guard1.is_some());
        assert!(guard2.is_some());
        assert!(guard3.is_some());
        assert!(guard4.is_none()); // Should fail, max is 3

        // Clean up
        drop(guard1);
        drop(guard2);
        drop(guard3);

        // Reset to default values
        reset_defaults();
    }
}
