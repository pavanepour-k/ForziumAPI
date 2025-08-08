//! Simple variable-size memory pool allocator

use pyo3::prelude::*;
use pyo3::types::PyByteArray;
use std::cell::RefCell;

/// Allocator that manages variable-size blocks up to a total capacity.
#[pyclass(module = "forzium_engine", unsendable)]
#[derive(Debug)]
pub struct PoolAllocator {
    capacity: usize,
    used: RefCell<usize>,
    blocks: RefCell<Vec<Vec<u8>>>,
}

impl PoolAllocator {
    /// Create a new pool with a byte capacity.
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity,
            used: RefCell::new(0),
            blocks: RefCell::new(Vec::new()),
        }
    }

    /// Acquire a block of *size* bytes from the pool.
    pub fn allocate(&self, size: usize) -> Option<Vec<u8>> {
        let mut used = self.used.borrow_mut();
        if *used + size > self.capacity {
            return None;
        }
        *used += size;
        if let Some(mut block) = self.blocks.borrow_mut().pop() {
            if block.len() < size {
                block.resize(size, 0);
            }
            Some(block)
        } else {
            Some(vec![0u8; size])
        }
    }

    /// Return a block back to the pool.
    pub fn deallocate(&self, block: Vec<u8>) {
        let len = block.len();
        *self.used.borrow_mut() -= len;
        self.blocks.borrow_mut().push(block);
    }

    /// Number of free bytes remaining.
    pub fn available(&self) -> usize {
        self.capacity - *self.used.borrow()
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

    #[staticmethod]
    #[pyo3(name = "create_numa_pools")]
    pub fn py_create_numa_pools(total: usize, nodes: usize) -> Vec<Self> {
        Self::new_numa(total, nodes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alloc_and_dealloc_cycle() {
        let pool = PoolAllocator::new(32);
        assert_eq!(pool.available(), 32);
        let b1 = pool.allocate(8).expect("first block");
        let b2 = pool.allocate(8).expect("second block");
        assert!(pool.allocate(40).is_none());
        pool.deallocate(b1);
        assert_eq!(pool.available(), 16);
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
}
