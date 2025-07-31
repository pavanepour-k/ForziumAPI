//! Simple fixed-size memory pool allocator

use std::cell::RefCell;

/// Allocator that manages a fixed number of blocks of equal size.
#[derive(Debug)]
pub struct PoolAllocator {
    block_size: usize,
    blocks: RefCell<Vec<Vec<u8>>>,
}

impl PoolAllocator {
    /// Create a new pool with the given block size and capacity.
    pub fn new(block_size: usize, capacity: usize) -> Self {
        let blocks = vec![vec![0u8; block_size]; capacity];
        Self {
            block_size,
            blocks: RefCell::new(blocks),
        }
    }

    /// Acquire a block from the pool.
    ///
    /// Returns `Some(Vec<u8>)` if a block is available, otherwise `None`.
    pub fn allocate(&self) -> Option<Vec<u8>> {
        self.blocks.borrow_mut().pop()
    }

    /// Return a block back to the pool.
    pub fn deallocate(&self, mut block: Vec<u8>) {
        if block.len() != self.block_size {
            block.resize(self.block_size, 0);
        }
        self.blocks.borrow_mut().push(block);
    }

    /// Current number of free blocks.
    pub fn available(&self) -> usize {
        self.blocks.borrow().len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alloc_and_dealloc_cycle() {
        let pool = PoolAllocator::new(8, 2);
        assert_eq!(pool.available(), 2);
        let b1 = pool.allocate().expect("first block");
        let b2 = pool.allocate().expect("second block");
        assert!(pool.allocate().is_none());
        pool.deallocate(b1);
        assert_eq!(pool.available(), 1);
        pool.deallocate(b2);
        assert_eq!(pool.available(), 2);
    }
}
