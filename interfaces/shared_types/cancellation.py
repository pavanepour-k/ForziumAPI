"""Cancellation token implementation for async operations.

This module provides a thread-safe cancellation token that can be used to signal
cancellation across different layers of the application, following Rust's
cancellation patterns for cooperative task termination.
"""

from __future__ import annotations

import threading


class CancellationToken:
    """Thread-safe token for cancelling long-running operations.
    
    This class provides a cooperative cancellation mechanism that allows
    long-running operations to be cancelled from other threads. It follows
    the same patterns as Rust's cancellation tokens for consistency.
    
    Example:
        >>> token = CancellationToken()
        >>> # In a long-running operation
        >>> if token.cancelled():
        ...     raise CancelledError("Operation was cancelled")
        >>> # From another thread
        >>> token.cancel()
    """
    
    def __init__(self) -> None:
        """Initialize a new cancellation token.
        
        The token starts in an uncancelled state.
        """
        self._cancelled = False
        self._lock = threading.Lock()
    
    def cancel(self) -> None:
        """Mark the token as cancelled.
        
        This method is thread-safe and can be called from any thread.
        Once cancelled, the token remains cancelled until reset() is called.
        """
        with self._lock:
            self._cancelled = True
    
    def cancelled(self) -> bool:
        """Check if the token has been cancelled.
        
        Returns:
            True if the token has been cancelled, False otherwise.
            
        This method is thread-safe and can be called from any thread.
        """
        with self._lock:
            return self._cancelled
    
    def reset(self) -> None:
        """Reset the token to uncancelled state.
        
        This method is thread-safe and can be called from any thread.
        Use with caution as it may cause previously cancelled operations
        to continue running.
        """
        with self._lock:
            self._cancelled = False


__all__ = ["CancellationToken"]