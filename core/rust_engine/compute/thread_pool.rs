use once_cell::sync::Lazy;
use parking_lot::RwLock;
use rayon::{ThreadPool, ThreadPoolBuilder};
use std::sync::Arc;
use std::time::Duration;

/// NUMA domain information
#[derive(Debug, Clone, Copy)]
pub struct NumaInfo {
    /// Number of NUMA nodes detected
    pub nodes: usize,
    /// Number of logical cores per node
    pub cores_per_node: usize,
    /// Total logical cores
    pub total_cores: usize,
}

/// Thread pool configuration settings
#[derive(Debug, Clone)]
pub struct ThreadPoolConfig {
    /// Number of threads in the pool
    pub thread_count: usize,
    /// Stack size for each thread in bytes
    pub stack_size: usize,
    /// Time to keep threads alive when idle
    pub thread_lifetime_ms: u64,
    /// Breadth-first or depth-first task execution
    pub breadth_first: bool,
    /// Automatic NUMA node affinity
    pub use_numa_affinity: bool,
}

impl Default for ThreadPoolConfig {
    fn default() -> Self {
        let cores = num_cpus::get();
        Self {
            thread_count: cores,
            stack_size: 2 * 1024 * 1024, // 2MB stack
            thread_lifetime_ms: 10000,   // 10 seconds
            breadth_first: false,        // Default depth-first
            use_numa_affinity: false,    // No NUMA affinity by default
        }
    }
}

/// Thread pool manager for Forzium compute operations
pub struct ThreadPoolManager {
    /// The default thread pool used for compute operations
    default_pool: Arc<ThreadPool>,
    /// Configuration used to create the default pool
    config: Arc<RwLock<ThreadPoolConfig>>,
    /// NUMA information if available
    numa_info: Option<NumaInfo>,
    /// Specialized pools for different workloads
    specialized_pools: Arc<RwLock<Vec<(String, Arc<ThreadPool>)>>>,
}

/// Global thread pool manager instance
static THREAD_POOL_MANAGER: Lazy<Arc<ThreadPoolManager>> = Lazy::new(|| {
    Arc::new(
        ThreadPoolManager::new(ThreadPoolConfig::default())
            .expect("Failed to create thread pool manager"),
    )
});

impl ThreadPoolManager {
    /// Create a new thread pool manager with the given configuration
    pub fn new(config: ThreadPoolConfig) -> Result<Self, String> {
        // Detect NUMA information
        let numa_info = Self::detect_numa();

        // Create the default thread pool
        let pool = Self::create_pool(&config)?;

        Ok(Self {
            default_pool: Arc::new(pool),
            config: Arc::new(RwLock::new(config)),
            numa_info,
            specialized_pools: Arc::new(RwLock::new(Vec::new())),
        })
    }

    /// Get the global thread pool manager instance
    pub fn global() -> &'static Arc<ThreadPoolManager> {
        &THREAD_POOL_MANAGER
    }

    /// Get the default thread pool
    pub fn pool(&self) -> &ThreadPool {
        &self.default_pool
    }

    /// Create a specialized thread pool for a specific workload
    pub fn create_specialized_pool(
        &self,
        name: &str,
        thread_count: usize,
    ) -> Result<Arc<ThreadPool>, String> {
        let mut config = self.config.read().clone();
        config.thread_count = thread_count;

        // Create a new pool with the modified config
        let pool = Arc::new(Self::create_pool(&config)?);

        // Store the pool
        self.specialized_pools
            .write()
            .push((name.to_string(), pool.clone()));

        Ok(pool)
    }

    /// Get a specialized pool by name, or create it if it doesn't exist
    pub fn get_or_create_specialized_pool(
        &self,
        name: &str,
        thread_count: usize,
    ) -> Result<Arc<ThreadPool>, String> {
        // Check if the pool already exists
        {
            let pools = self.specialized_pools.read();
            for (pool_name, pool) in pools.iter() {
                if pool_name == name {
                    return Ok(pool.clone());
                }
            }
        }

        // Create a new pool if it doesn't exist
        self.create_specialized_pool(name, thread_count)
    }

    /// Update the thread pool configuration
    pub fn update_config(&self, new_config: ThreadPoolConfig) -> Result<(), String> {
        // Store the new configuration
        *self.config.write() = new_config.clone();

        // We can't update existing thread pools, so they'll continue with their old configuration
        // New pools created after this point will use the new configuration

        Ok(())
    }

    /// Get the current thread pool configuration
    pub fn get_config(&self) -> ThreadPoolConfig {
        self.config.read().clone()
    }

    /// Get NUMA information if available
    pub fn get_numa_info(&self) -> Option<NumaInfo> {
        self.numa_info
    }

    /// Create a thread pool with the given configuration
    fn create_pool(config: &ThreadPoolConfig) -> Result<ThreadPool, String> {
        let mut builder = ThreadPoolBuilder::new()
            .num_threads(config.thread_count)
            .stack_size(config.stack_size)
            .thread_name(|idx| format!("forzium-worker-{}", idx));

        if config.breadth_first {
            builder = builder.breadth_first();
        }

        // Set thread lifetime
        if config.thread_lifetime_ms > 0 {
            let duration = Duration::from_millis(config.thread_lifetime_ms);
            builder = builder.thread_lifetime(duration);
        }

        // Build the thread pool
        builder
            .build()
            .map_err(|e| format!("Failed to create thread pool: {}", e))
    }

    /// Detect NUMA information
    fn detect_numa() -> Option<NumaInfo> {
        // This is a simple approximation as Rust doesn't have good NUMA detection
        // In a real implementation, you'd use platform-specific libraries or hwloc

        let total_cores = num_cpus::get();
        let physical_cores = num_cpus::get_physical();

        // Heuristic: assume each physical CPU package is a NUMA node
        // This is a simplification but often works for basic systems
        let estimated_numa_nodes = if physical_cores > 0 && total_cores >= physical_cores {
            // Estimate number of NUMA nodes (physical CPUs)
            let hyperthreading_factor = total_cores / physical_cores;
            if hyperthreading_factor > 0 {
                physical_cores / hyperthreading_factor
            } else {
                1
            }
        } else {
            1 // Default to 1 NUMA node if detection fails
        };

        if estimated_numa_nodes > 0 {
            Some(NumaInfo {
                nodes: estimated_numa_nodes,
                cores_per_node: total_cores / estimated_numa_nodes,
                total_cores,
            })
        } else {
            None
        }
    }
}

/// Initialize the thread pool system with optimal settings
pub fn initialize_optimal_thread_pools() -> Result<(), String> {
    // Detect system resources
    let total_cores = num_cpus::get();
    let physical_cores = num_cpus::get_physical();

    // Calculate optimal thread count (avoid oversubscription)
    let optimal_threads = if physical_cores > 0 {
        // Use physical core count + 1 as a good default
        // This avoids excessive context switching while still
        // taking advantage of all cores
        physical_cores + 1
    } else {
        // Fallback: use 3/4 of logical cores
        (total_cores * 3) / 4
    }
    .max(1); // Ensure at least one thread

    // Create optimal configuration
    let config = ThreadPoolConfig {
        thread_count: optimal_threads,
        stack_size: 2 * 1024 * 1024, // 2MB is a good default
        thread_lifetime_ms: 30000,   // 30 second thread lifetime
        breadth_first: false,        // Depth-first is usually better for compute
        use_numa_affinity: true,     // Enable NUMA awareness
    };

    // Initialize the global thread pool with our settings
    let manager = ThreadPoolManager::global();
    manager.update_config(config)?;

    // Create specialized pools for different workloads

    // Small pool for IO-bound or light work
    let io_threads = (total_cores / 4).max(2);
    manager.create_specialized_pool("io", io_threads)?;

    // Large pool for compute-intensive workloads
    let compute_threads = optimal_threads;
    manager.create_specialized_pool("compute", compute_threads)?;

    // Numa-aware pools if we have multiple NUMA nodes
    if let Some(numa_info) = manager.get_numa_info() {
        if numa_info.nodes > 1 {
            // Create a pool per NUMA node
            for node in 0..numa_info.nodes {
                // In a real implementation, you would set NUMA affinity here
                // using platform-specific APIs
                manager
                    .create_specialized_pool(&format!("numa_{}", node), numa_info.cores_per_node)?;
            }
        }
    }

    Ok(())
}

/// Run a function in the compute thread pool
pub fn run_in_compute_pool<F, R>(f: F) -> R
where
    F: FnOnce() -> R + Send,
    R: Send,
{
    let manager = ThreadPoolManager::global();
    let pool = manager
        .get_or_create_specialized_pool("compute", num_cpus::get())
        .expect("Failed to get compute thread pool");

    pool.install(f)
}

/// Run a function in the IO thread pool
pub fn run_in_io_pool<F, R>(f: F) -> R
where
    F: FnOnce() -> R + Send,
    R: Send,
{
    let manager = ThreadPoolManager::global();
    let pool = manager
        .get_or_create_specialized_pool("io", (num_cpus::get() / 4).max(2))
        .expect("Failed to get IO thread pool");

    pool.install(f)
}

/// Configure the global thread pool with custom settings
pub fn configure_global_thread_pool(
    thread_count: usize,
    stack_size: usize,
    thread_lifetime_ms: u64,
    breadth_first: bool,
) -> Result<(), String> {
    let config = ThreadPoolConfig {
        thread_count,
        stack_size,
        thread_lifetime_ms,
        breadth_first,
        use_numa_affinity: true,
    };

    ThreadPoolManager::global().update_config(config)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[test]
    fn test_thread_pool_creation() {
        let config = ThreadPoolConfig::default();
        let manager = ThreadPoolManager::new(config).unwrap();
        let pool = manager.pool();

        // Test that the pool works correctly
        let counter = AtomicUsize::new(0);

        pool.install(|| {
            (0..1000).into_iter().for_each(|_| {
                counter.fetch_add(1, Ordering::SeqCst);
            });
        });

        assert_eq!(counter.load(Ordering::SeqCst), 1000);
    }

    #[test]
    fn test_specialized_pools() {
        let manager = ThreadPoolManager::global();

        // Create specialized pools
        let compute_pool = manager
            .get_or_create_specialized_pool("test_compute", 4)
            .unwrap();
        let io_pool = manager
            .get_or_create_specialized_pool("test_io", 2)
            .unwrap();

        // Test that both pools work correctly
        let compute_counter = AtomicUsize::new(0);
        let io_counter = AtomicUsize::new(0);

        compute_pool.install(|| {
            (0..1000).into_iter().for_each(|_| {
                compute_counter.fetch_add(1, Ordering::SeqCst);
            });
        });

        io_pool.install(|| {
            (0..1000).into_iter().for_each(|_| {
                io_counter.fetch_add(1, Ordering::SeqCst);
            });
        });

        assert_eq!(compute_counter.load(Ordering::SeqCst), 1000);
        assert_eq!(io_counter.load(Ordering::SeqCst), 1000);
    }
}
