//! Thread-safe variable-size memory pool allocator

use parking_lot::RwLock as PlRwLock;
use pyo3::prelude::*;
use pyo3::types::PyByteArray;
use std::collections::VecDeque;
use std::sync::{Arc, Mutex, RwLock};
use std::time::{Duration, Instant};

/// Statistics about memory pool usage
#[derive(Debug, Clone, Copy)]
pub struct PoolStats {
    /// Total capacity of the pool in bytes
    pub capacity: usize,
    /// Current used bytes in the pool
    pub used: usize,
    /// Number of allocations performed
    pub alloc_count: usize,
    /// Number of deallocations performed
    pub dealloc_count: usize,
    /// Number of allocation retries due to contention
    pub contention_count: usize,
    /// Maximum used bytes during pool lifetime
    pub peak_usage: usize,
    /// Time of last allocation in seconds since pool creation
    pub last_alloc_time: f64,
}

/// Allocator that manages thread-safe variable-size memory blocks up to a total capacity.
#[pyclass(module = "forzium_engine")]
#[derive(Debug, Clone)]
pub struct PoolAllocator {
    capacity: usize,
    // Use parking_lot RwLock for better performance
    used: Arc<PlRwLock<usize>>,
    peak_usage: Arc<PlRwLock<usize>>,
    blocks: Arc<Mutex<VecDeque<Vec<u8>>>>,
    stats: Arc<PlRwLock<PoolStats>>,
    creation_time: Arc<Instant>,
}

impl PoolAllocator {
    /// Create a new pool with a byte capacity.
    pub fn new(capacity: usize) -> Self {
        let now = Instant::now();
        Self {
            capacity,
            used: Arc::new(PlRwLock::new(0)),
            peak_usage: Arc::new(PlRwLock::new(0)),
            blocks: Arc::new(Mutex::new(VecDeque::new())),
            stats: Arc::new(PlRwLock::new(PoolStats {
                capacity,
                used: 0,
                alloc_count: 0,
                dealloc_count: 0,
                contention_count: 0,
                peak_usage: 0,
                last_alloc_time: 0.0,
            })),
            creation_time: Arc::new(now),
        }
    }

    /// Acquire a block of *size* bytes from the pool with timeout and retry
    pub fn allocate(&self, size: usize) -> Option<Vec<u8>> {
        const MAX_RETRIES: usize = 3;
        const RETRY_DELAY_MS: u64 = 10;

        let mut retries = 0;
        let now = Instant::now();

        while retries < MAX_RETRIES {
            // First check if we have enough capacity (read-only)
            {
                let used = self.used.read();
                if *used + size > self.capacity {
                    return None;
                }
            }

            // Try to acquire a mutex on the blocks
            if let Ok(mut blocks) = self.blocks.try_lock() {
                // Update used counter
                let mut used = self.used.write();
                *used += size;

                // Update peak usage if needed
                let mut peak = self.peak_usage.write();
                if *used > *peak {
                    *peak = *used;
                }

                // Get a block from the pool or create a new one
                let block = if let Some(mut block) = blocks.pop_front() {
                    if block.len() < size {
                        block.resize(size, 0);
                    }
                    block
                } else {
                    vec![0u8; size]
                };

                // Update stats
                let elapsed = now.duration_since(*self.creation_time).as_secs_f64();
                let mut stats = self.stats.write();
                stats.used = *used;
                stats.alloc_count += 1;
                stats.contention_count += retries;
                stats.peak_usage = *peak;
                stats.last_alloc_time = elapsed;

                return Some(block);
            }

            // If we couldn't get the lock, increment contention counter and retry
            retries += 1;
            std::thread::sleep(Duration::from_millis(RETRY_DELAY_MS));
        }

        // Couldn't acquire the lock after retries
        let mut stats = self.stats.write();
        stats.contention_count += retries;
        None
    }

    /// Return a block back to the pool.
    pub fn deallocate(&self, block: Vec<u8>) {
        let len = block.len();

        // Update used counter
        {
            let mut used = self.used.write();
            *used = used.saturating_sub(len);
        }

        // Return block to the pool if we can acquire the mutex
        if let Ok(mut blocks) = self.blocks.try_lock() {
            blocks.push_back(block);

            // Update stats
            let mut stats = self.stats.write();
            stats.used = *self.used.read();
            stats.dealloc_count += 1;
        } else {
            // If can't acquire mutex, just drop the block
            // This is a compromise to avoid deadlocks
            // We've already updated the used counter so memory accounting is correct
        }
    }

    /// Number of free bytes remaining.
    pub fn available(&self) -> usize {
        self.capacity - *self.used.read()
    }

    /// Get current statistics about the pool
    pub fn stats(&self) -> PoolStats {
        *self.stats.read()
    }

    /// Create *nodes* pools dividing *total* capacity equally.
    pub fn new_numa(total: usize, nodes: usize) -> Vec<Self> {
        let per = total / nodes.max(1);
        (0..nodes.max(1)).map(|_| Self::new(per)).collect()
    }
}

#[pymethods]
impl PoolAllocator {
    #[new]
    pub fn py_new(capacity: usize) -> Self {
        Self::new(capacity)
    }

    #[pyo3(name = "allocate")]
    pub fn py_allocate(&self, py: Python<'_>, size: usize) -> Option<Py<PyByteArray>> {
        self.allocate(size)
            .map(|vec| PyByteArray::new(py, &vec).into())
    }

    #[pyo3(name = "deallocate")]
    pub fn py_deallocate(&self, data: Vec<u8>) {
        self.deallocate(data);
    }

    #[pyo3(name = "available")]
    pub fn py_available(&self) -> usize {
        self.available()
    }

    #[pyo3(name = "get_stats")]
    pub fn py_get_stats(&self, py: Python<'_>) -> PyObject {
        let stats = self.stats();
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("capacity", stats.capacity).unwrap();
        dict.set_item("used", stats.used).unwrap();
        dict.set_item("alloc_count", stats.alloc_count).unwrap();
        dict.set_item("dealloc_count", stats.dealloc_count).unwrap();
        dict.set_item("contention_count", stats.contention_count)
            .unwrap();
        dict.set_item("peak_usage", stats.peak_usage).unwrap();
        dict.set_item("last_alloc_time", stats.last_alloc_time)
            .unwrap();
        dict.set_item(
            "utilization_pct",
            (stats.used as f64 / stats.capacity as f64) * 100.0,
        )
        .unwrap();
        dict.into()
    }

    #[staticmethod]
    #[pyo3(name = "create_numa_pools")]
    pub fn py_create_numa_pools(total: usize, nodes: usize) -> Vec<Self> {
        Self::new_numa(total, nodes)
    }

    /// Create a thread-safe memory pool that can be shared across threads
    #[staticmethod]
    #[pyo3(name = "create_shared_pool")]
    pub fn py_create_shared_pool(capacity: usize) -> Self {
        Self::new(capacity)
    }

    /// Clone this pool to create another reference to the same underlying memory pool
    pub fn clone(&self) -> Self {
        Self {
            capacity: self.capacity,
            used: self.used.clone(),
            peak_usage: self.peak_usage.clone(),
            blocks: self.blocks.clone(),
            stats: self.stats.clone(),
            creation_time: self.creation_time.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn alloc_and_dealloc_cycle() {
        let pool = PoolAllocator::new(32);
        assert_eq!(pool.available(), 32);
        let b1 = pool.allocate(8).expect("first block");
        let b2 = pool.allocate(8).expect("second block");
        assert!(pool.allocate(40).is_none());
        pool.deallocate(b1);
        assert_eq!(pool.available(), 24);
        pool.deallocate(b2);
        assert_eq!(pool.available(), 32);
    }

    #[test]
    fn create_numa_pools_split_capacity() {
        let pools = PoolAllocator::new_numa(100, 4);
        assert_eq!(pools.len(), 4);
        for p in pools {
            assert_eq!(p.available(), 25);
        }
    }

    #[test]
    fn test_thread_safety() {
        // Create a pool with 1MB capacity
        let pool = Arc::new(PoolAllocator::new(1_000_000));

        // Spawn 10 threads that each allocate and deallocate blocks
        let mut handles = vec![];
        for _ in 0..10 {
            let pool_clone = pool.clone();
            let handle = thread::spawn(move || {
                for _ in 0..100 {
                    // Allocate and deallocate blocks of different sizes
                    if let Some(block) = pool_clone.allocate(1024) {
                        // Do something with the block
                        pool_clone.deallocate(block);
                    }

                    if let Some(block) = pool_clone.allocate(4096) {
                        // Do something with the block
                        pool_clone.deallocate(block);
                    }
                }
            });
            handles.push(handle);
        }

        // Wait for all threads to complete
        for handle in handles {
            handle.join().unwrap();
        }

        // Check that all memory was returned to the pool
        assert_eq!(pool.available(), 1_000_000);

        // Check stats
        let stats = pool.stats();
        assert!(stats.alloc_count > 0);
        assert_eq!(stats.alloc_count, stats.dealloc_count);
    }

    #[test]
    fn test_peak_usage() {
        let pool = PoolAllocator::new(1000);

        // Allocate blocks to reach peak usage
        let b1 = pool.allocate(400).unwrap();
        let b2 = pool.allocate(400).unwrap();

        // Deallocate one block
        pool.deallocate(b1);

        // The peak usage should still be 800
        let stats = pool.stats();
        assert_eq!(stats.peak_usage, 800);
    }
}
