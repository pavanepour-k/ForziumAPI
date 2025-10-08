"""Tests for orchestration service."""

import pytest
from unittest.mock import Mock, patch
from core.service.orchestration_service import run_computation, stream_computation


class TestOrchestrationService:
    """Test orchestration service functionality."""

    def test_run_computation_with_engine(self):
        """Test computation with Rust engine available."""
        with patch('core.service.orchestration_service.ENGINE') as mock_engine:
            mock_engine.supports.return_value = True
            mock_engine.compute.return_value = [[2.0, 4.0]]
            
            data = [[1.0, 2.0]]
            operation = "multiply"
            parameters = {"factor": 2.0}
            
            result = run_computation(data, operation, parameters)
            
            assert "result" in result
            assert "execution_time_ms" in result
            assert "memory_usage_mb" in result
            assert "rust_operations_count" in result
            assert result["result"] == [[2.0, 4.0]]

    def test_run_computation_fallback_python(self):
        """Test computation fallback to Python implementation."""
        with patch('core.service.orchestration_service.ENGINE', None):
            data = [[1.0, 2.0]]
            operation = "multiply"
            parameters = {"factor": 2.0}
            
            result = run_computation(data, operation, parameters)
            
            assert "result" in result
            assert result["result"] == [[2.0, 4.0]]

    def test_run_computation_add_operation(self):
        """Test add operation."""
        with patch('core.service.orchestration_service.ENGINE', None):
            data = [[1.0, 2.0]]
            operation = "add"
            parameters = {"addend": 5.0}
            
            result = run_computation(data, operation, parameters)
            
            assert result["result"] == [[6.0, 7.0]]

    def test_run_computation_matmul_operation(self):
        """Test matrix multiplication operation."""
        with patch('core.service.orchestration_service.ENGINE', None):
            data = [[1.0, 2.0]]
            operation = "matmul"
            parameters = {"matrix_b": [[3.0], [4.0]]}
            
            result = run_computation(data, operation, parameters)
            
            assert result["result"] == [[11.0]]

    def test_run_computation_unsupported_operation(self):
        """Test unsupported operation raises error."""
        with patch('core.service.orchestration_service.ENGINE', None):
            data = [[1.0, 2.0]]
            operation = "unsupported"
            parameters = {}
            
            with pytest.raises(ValueError, match="Unsupported operation"):
                run_computation(data, operation, parameters)

    def test_run_computation_cancelled(self):
        """Test computation cancellation."""
        from interfaces.shared_types.cancellation import CancellationToken
        
        token = CancellationToken()
        token.cancel()
        
        data = [[1.0, 2.0]]
        operation = "multiply"
        parameters = {"factor": 2.0}
        
        with pytest.raises(RuntimeError, match="operation cancelled"):
            run_computation(data, operation, parameters, token)

    def test_stream_computation(self):
        """Test streaming computation."""
        with patch('core.service.orchestration_service.ENGINE', None):
            data = [[1.0, 2.0], [3.0, 4.0]]
            operation = "multiply"
            parameters = {"factor": 2.0}
            
            results = list(stream_computation(data, operation, parameters))
            
            assert len(results) == 2
            assert results[0] == [2.0, 4.0]
            assert results[1] == [6.0, 8.0]

    def test_stream_computation_cancelled(self):
        """Test streaming computation cancellation."""
        from interfaces.shared_types.cancellation import CancellationToken
        
        token = CancellationToken()
        token.cancel()
        
        data = [[1.0, 2.0]]
        operation = "multiply"
        parameters = {"factor": 2.0}
        
        with pytest.raises(RuntimeError, match="operation cancelled"):
            list(stream_computation(data, operation, parameters, token))
