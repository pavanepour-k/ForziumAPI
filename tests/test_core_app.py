"""Tests for core application endpoints."""

import pytest
from unittest.mock import Mock, patch
from core.app import app, server


class TestCoreApp:
    """Test core application functionality."""

    def test_health_endpoint(self):
        """Test health check endpoint."""
        # Mock the server and app
        with patch('core.app.server') as mock_server:
            mock_server.add_route = Mock()
            from core.app import health
            
            result = health()
            assert result == {"status": "ok"}

    def test_compute_endpoint_valid_request(self):
        """Test compute endpoint with valid request."""
        with patch('core.app.run_computation') as mock_run:
            mock_run.return_value = {"result": [[1.0, 2.0]], "execution_time_ms": 1.0}
            
            from core.app import compute
            
            payload = {
                "data": [[1.0, 2.0]],
                "operation": "multiply",
                "parameters": {"factor": 2.0}
            }
            
            result = compute(payload)
            assert "result" in result
            assert "execution_time_ms" in result

    def test_compute_endpoint_invalid_request(self):
        """Test compute endpoint with invalid request."""
        from core.app import compute
        
        payload = {"invalid": "data"}
        
        result = compute(payload)
        assert isinstance(result, tuple)
        assert result[0] == 422
        assert "detail" in result[1]

    def test_stream_endpoint_valid_request(self):
        """Test stream endpoint with valid request."""
        with patch('core.app.stream_computation') as mock_stream:
            mock_stream.return_value = iter([[1.0, 2.0], [3.0, 4.0]])
            
            from core.app import stream
            
            payload = {
                "data": [[1.0, 2.0], [3.0, 4.0]],
                "operation": "multiply",
                "parameters": {"factor": 2.0}
            }
            
            result = stream(payload)
            assert hasattr(result, 'body_iterator')

    def test_secure_data_endpoint(self):
        """Test secure data endpoint."""
        with patch('core.app.api_key_query') as mock_auth:
            mock_auth.return_value = "valid_key"
            
            from core.app import secure_data
            
            result = secure_data(api_key="valid_key")
            assert result == {"message": "secured"}
