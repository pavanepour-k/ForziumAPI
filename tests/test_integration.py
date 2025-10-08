"""Integration tests for Forzium API."""

import pytest
from unittest.mock import Mock, patch
import json


class TestIntegration:
    """Integration tests for the complete system."""

    def test_health_endpoint_integration(self):
        """Test health endpoint integration."""
        with patch('core.app.server') as mock_server:
            from core.app import health
            
            result = health()
            assert result == {"status": "ok"}

    def test_compute_workflow_integration(self):
        """Test complete compute workflow."""
        with patch('core.service.orchestration_service.ENGINE') as mock_engine:
            mock_engine.supports.return_value = True
            mock_engine.compute.return_value = [[2.0, 4.0]]
            
            from core.app import compute
            
            payload = {
                "data": [[1.0, 2.0]],
                "operation": "multiply",
                "parameters": {"factor": 2.0}
            }
            
            result = compute(payload)
            
            assert "result" in result
            assert "execution_time_ms" in result
            assert result["result"] == [[2.0, 4.0]]

    def test_stream_workflow_integration(self):
        """Test complete streaming workflow."""
        with patch('core.service.orchestration_service.ENGINE') as mock_engine:
            mock_engine.supports.return_value = True
            mock_engine.compute.return_value = [[2.0, 4.0], [6.0, 8.0]]
            
            from core.app import stream
            
            payload = {
                "data": [[1.0, 2.0], [3.0, 4.0]],
                "operation": "multiply",
                "parameters": {"factor": 2.0}
            }
            
            result = stream(payload)
            
            # Test streaming response
            chunks = list(result.body_iterator)
            assert len(chunks) == 2
            
            # Parse JSON chunks
            chunk1 = json.loads(chunks[0].decode())
            chunk2 = json.loads(chunks[1].decode())
            
            assert chunk1 == [2.0, 4.0]
            assert chunk2 == [6.0, 8.0]

    def test_error_handling_integration(self):
        """Test error handling in complete workflow."""
        from core.app import compute
        
        # Test invalid payload
        payload = {"invalid": "data"}
        result = compute(payload)
        
        assert isinstance(result, tuple)
        assert result[0] == 422
        assert "detail" in result[1]

    def test_security_integration(self):
        """Test security endpoint integration."""
        with patch('core.app.api_key_query') as mock_auth:
            mock_auth.return_value = "valid_key"
            
            from core.app import secure_data
            
            result = secure_data(api_key="valid_key")
            assert result == {"message": "secured"}

    def test_memory_pool_integration(self):
        """Test memory pool integration."""
        from core.service.orchestration_service import PoolAllocator
        
        # Test fallback PoolAllocator
        pool = PoolAllocator(1024)
        
        # Test allocation
        block = pool.allocate(64)
        assert len(block) == 64
        assert pool.available() == 960
        
        # Test deallocation
        pool.deallocate(block)
        assert pool.available() == 1024

    def test_cancellation_integration(self):
        """Test cancellation token integration."""
        from interfaces.shared_types.cancellation import CancellationToken
        from core.service.orchestration_service import run_computation
        
        token = CancellationToken()
        token.cancel()
        
        data = [[1.0, 2.0]]
        operation = "multiply"
        parameters = {"factor": 2.0}
        
        with pytest.raises(RuntimeError, match="operation cancelled"):
            run_computation(data, operation, parameters, token)
