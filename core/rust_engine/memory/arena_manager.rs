//! Arena allocator managing multiple memory pools

use super::pool_allocator::PoolAllocator;

/// Central manager coordinating several memory pools for different sizes.
pub struct ArenaManager {
    small: PoolAllocator,
    medium: PoolAllocator,
}

impl ArenaManager {
    /// Create an arena manager with default pool sizes.
    pub fn new() -> Self {
        Self {
            small: PoolAllocator::new(64, 128),
            medium: PoolAllocator::new(256, 64),
        }
    }

    /// Allocate a buffer of roughly `size` bytes.
    pub fn allocate(&self, size: usize) -> Option<Vec<u8>> {
        if size <= 64 {
            self.small.allocate()
        } else if size <= 256 {
            self.medium.allocate()
        } else {
            None
        }
    }

    /// Return a buffer for reuse.
    pub fn deallocate(&self, buffer: Vec<u8>) {
        let len = buffer.len();
        if len <= 64 {
            self.small.deallocate(buffer);
        } else if len <= 256 {
            self.medium.deallocate(buffer);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allocate_small_and_medium() {
        let arena = ArenaManager::new();
        let s = arena.allocate(32).expect("small alloc");
        assert_eq!(s.len(), 64); // block size
        let m = arena.allocate(128).expect("medium alloc");
        assert_eq!(m.len(), 256);
        assert!(arena.allocate(1024).is_none());
        arena.deallocate(s);
        arena.deallocate(m);
        assert!(arena.allocate(64).is_some());
    }
}
