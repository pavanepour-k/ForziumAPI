"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def mock_engine():
    """Mock the Rust compute engine."""
    with patch('core.service.orchestration_service.ENGINE') as mock:
        mock.supports.return_value = True
        mock.compute.return_value = [[1.0, 2.0]]
        yield mock


@pytest.fixture
def mock_server():
    """Mock the HTTP server."""
    with patch('core.app.server') as mock:
        mock.add_route = Mock()
        yield mock


@pytest.fixture
def sample_matrix():
    """Sample matrix data for testing."""
    return [[1.0, 2.0], [3.0, 4.0]]


@pytest.fixture
def sample_compute_request():
    """Sample compute request data."""
    return {
        "data": [[1.0, 2.0], [3.0, 4.0]],
        "operation": "multiply",
        "parameters": {"factor": 2.0}
    }


@pytest.fixture
def cancellation_token():
    """Cancellation token for testing."""
    from interfaces.shared_types.cancellation import CancellationToken
    return CancellationToken()


@pytest.fixture(autouse=True)
def disable_gpu():
    """Disable GPU for consistent testing."""
    with patch('core.service.gpu.USE_GPU', False):
        yield
