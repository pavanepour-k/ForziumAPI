"""Tests for Forzium application framework."""

import pytest
from unittest.mock import Mock, patch
from forzium import ForziumApp, Depends, ComputeRequest


class TestForziumApp:
    """Test Forzium application framework."""

    def test_app_creation(self):
        """Test ForziumApp creation."""
        with patch('forzium_engine.ForziumHttpServer') as mock_server:
            app = ForziumApp(mock_server)
            assert app is not None

    def test_route_registration(self):
        """Test route registration."""
        with patch('forzium_engine.ForziumHttpServer') as mock_server:
            app = ForziumApp(mock_server)
            
            @app.get("/test")
            def test_route():
                return {"message": "test"}
            
            # Verify route was registered
            mock_server.add_route.assert_called()

    def test_dependency_injection(self):
        """Test dependency injection system."""
        def get_db():
            return "database"
        
        with patch('forzium_engine.ForziumHttpServer') as mock_server:
            app = ForziumApp(mock_server)
            
            @app.get("/test")
            def test_route(db: str = Depends(get_db)):
                return {"db": db}
            
            # Verify route was registered with dependency
            mock_server.add_route.assert_called()

    def test_compute_request_validation(self):
        """Test ComputeRequest validation."""
        # Valid request
        request_data = {
            "data": [[1.0, 2.0], [3.0, 4.0]],
            "operation": "multiply",
            "parameters": {"factor": 2.0}
        }
        
        request = ComputeRequest(**request_data)
        assert request.data == [[1.0, 2.0], [3.0, 4.0]]
        assert request.operation == "multiply"
        assert request.parameters == {"factor": 2.0}

    def test_compute_request_default_parameters(self):
        """Test ComputeRequest with default parameters."""
        request_data = {
            "data": [[1.0, 2.0]],
            "operation": "add"
        }
        
        request = ComputeRequest(**request_data)
        assert request.parameters == {}

    def test_compute_request_invalid_data(self):
        """Test ComputeRequest with invalid data."""
        request_data = {
            "data": [],  # Empty data
            "operation": "multiply"
        }
        
        with pytest.raises(ValueError):
            ComputeRequest(**request_data)
