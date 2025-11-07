"""
Tests for the FFI boundary between Python and Rust.

This module verifies the correctness of data passing between 
Python and Rust, error handling, and memory management.
"""

import unittest
import numpy as np
import gc
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

# Import the Rust engine
import forzium_engine as fe
from forzium._ffi.validation import ComputeRequest


class TestFFIBasics(unittest.TestCase):
    """Test basic FFI functionality"""
    
    def test_simple_operations(self):
        """Test that simple operations work across the FFI boundary"""
        # Test scalar operations
        self.assertEqual(fe.echo_u64(42), 42)
        
        # Test no-op function
        fe.noop()  # Should not raise
    
    def test_matrix_operations(self):
        """Test matrix operations across FFI boundary"""
        matrix = [[1.0, 2.0], [3.0, 4.0]]
        
        # Test multiplication
        result = fe.multiply(matrix, 2.0)
        expected = [[2.0, 4.0], [6.0, 8.0]]
        self.assertEqual(result, expected)
        
        # Test addition
        result = fe.add(matrix, 1.0)
        expected = [[2.0, 3.0], [4.0, 5.0]]
        self.assertEqual(result, expected)
    
    def test_error_handling(self):
        """Test that errors are correctly propagated"""
        # Test matrix shape mismatch
        matrix_a = [[1.0, 2.0], [3.0, 4.0]]
        matrix_b = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        
        with self.assertRaises(RuntimeError):
            fe.matmul(matrix_a, matrix_b)


class TestFFIMemoryManagement(unittest.TestCase):
    """Test memory management across FFI boundary"""
    
    def test_large_matrix_operations(self):
        """Test operations on large matrices to verify memory handling"""
        # Create a large matrix
        size = 1000
        large_matrix = [[float(i+j) for i in range(size)] for j in range(size)]
        
        # Perform operations that should trigger memory allocations
        result1 = fe.multiply(large_matrix, 2.0)
        result2 = fe.transpose(large_matrix)
        
        # Verify results
        self.assertEqual(result1[0][0], large_matrix[0][0] * 2.0)
        self.assertEqual(result2[0][0], large_matrix[0][0])
    
    def test_memory_pool(self):
        """Test the thread-safe memory pool"""
        # Create a pool
        pool = fe.PoolAllocator(1_000_000)
        
        # Allocate and deallocate
        data = pool.allocate(1024)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1024)
        
        # Check available memory
        self.assertEqual(pool.available(), 1_000_000 - 1024)
        
        # Deallocate
        pool.deallocate(data)
        self.assertEqual(pool.available(), 1_000_000)
        
        # Get stats
        stats = pool.get_stats()
        self.assertEqual(stats["alloc_count"], 1)
        self.assertEqual(stats["dealloc_count"], 1)
    
    def test_gc_interaction(self):
        """Test interaction with Python's garbage collector"""
        # Create a reference cycle with Rust objects
        a = fe.PoolAllocator(1000)
        b = {"pool": a}
        a._ref = b  # Create reference cycle
        
        # Get a weak reference
        import weakref
        weak_a = weakref.ref(a)
        
        # Delete references and force collection
        del a, b
        gc.collect()
        
        # Verify object was collected
        self.assertIsNone(weak_a())


class TestFFIConcurrency(unittest.TestCase):
    """Test concurrent access to Rust functions"""
    
    def test_thread_safety(self):
        """Test thread-safe access to Rust functions"""
        matrix = [[1.0, 2.0], [3.0, 4.0]]
        results = []
        errors = []
        
        def worker():
            try:
                # Call Rust from a Python thread
                result = fe.multiply(matrix, 2.0)
                results.append(result)
                return True
            except Exception as e:
                errors.append(e)
                return False
        
        # Run in multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify results
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 10)
        expected = [[2.0, 4.0], [6.0, 8.0]]
        for result in results:
            self.assertEqual(result, expected)
    
    def test_gil_release(self):
        """Test that compute-intensive operations release the GIL"""
        # Create large matrices for multiplication
        size = 500
        matrix_a = [[float(i+j) for i in range(size)] for j in range(size)]
        matrix_b = [[float(i*j) for i in range(size)] for j in range(size)]
        
        # Variable to track parallel execution
        parallel_execution = {'success': False}
        
        def gil_holding_thread():
            """This thread will hold the GIL for counting"""
            count = 0
            # Count for some time while the matrix multiplication happens
            end_time = time.time() + 1.0  # Run for 1 second
            while time.time() < end_time:
                count += 1
            # If count is high enough, the GIL was released by the other operation
            parallel_execution['success'] = count > 1000
        
        def matrix_thread():
            """This thread will perform the matrix multiplication"""
            # Use the SIMD-optimized multiply which releases the GIL
            fe.simd_matmul(matrix_a, matrix_b)
        
        # Start both threads
        t1 = threading.Thread(target=gil_holding_thread)
        t2 = threading.Thread(target=matrix_thread)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Verify that parallel execution happened
        self.assertTrue(parallel_execution['success'])


class TestFFIErrorHandling(unittest.TestCase):
    """Test error handling across FFI boundary"""
    
    def test_error_propagation(self):
        """Test that Rust errors are correctly propagated to Python"""
        # Test forced panic
        with self.assertRaises(RuntimeError):
            fe.trigger_panic()
        
        # Test validation error
        with self.assertRaises(ValueError):
            # Create an invalid matrix (ragged)
            invalid_matrix = [[1.0, 2.0], [3.0]]
            fe.multiply(invalid_matrix, 2.0)
    
    def test_error_details(self):
        """Test that error details are preserved"""
        # Enable verbose errors
        fe.set_verbose_errors(True)
        
        try:
            # Try an operation that will fail
            fe.matmul([[1.0]], [[1.0, 2.0]])
            self.fail("Should have raised an exception")
        except Exception as e:
            # Check that the error message contains useful details
            error_msg = str(e).lower()
            self.assertIn("shape", error_msg)
        
        # Test last error
        last_error = fe.get_last_error()
        self.assertNotEqual(last_error, "")


class TestFFIComplexDataTypes(unittest.TestCase):
    """Test handling of complex data types across FFI boundary"""
    
    def test_compute_request_schema(self):
        """Test the ComputeRequestSchema validation"""
        # Create a ComputeRequest using the FFI validation
        data = {
            "data": [[1.0, 2.0], [3.0, 4.0]],
            "operation": "multiply",
            "parameters": {"factor": 2.0}
        }
        
        request = ComputeRequest(**data)
        
        # Verify the data was correctly validated
        self.assertEqual(request.data, data["data"])
        self.assertEqual(request.operation, data["operation"])
        self.assertEqual(request.parameters, data["parameters"])
        
        # Test serialization
        json_str = request.json()
        self.assertIn("data", json_str)
        self.assertIn("operation", json_str)
        self.assertIn("parameters", json_str)


if __name__ == "__main__":
    unittest.main()
