"""
Pytest configuration and shared fixtures for Forzium API test suite.

This module provides common test fixtures, utilities, and configuration
for all test modules across the test suite.
"""

import gc
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Session-level fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root_dir() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root_dir: Path) -> Path:
    """Return the test data directory."""
    data_dir = project_root_dir / "tests" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Module-level fixtures
# ============================================================================

@pytest.fixture(scope="module")
def rust_engine_available() -> bool:
    """Check if Rust engine is available."""
    try:
        import forzium_engine
        return hasattr(forzium_engine, "multiply")
    except ImportError:
        return False


# ============================================================================
# Function-level fixtures
# ============================================================================

@pytest.fixture
def cleanup_gc():
    """Force garbage collection before and after test."""
    gc.collect()
    yield
    gc.collect()


@pytest.fixture
def small_matrix() -> List[List[float]]:
    """Provide a small 2x2 test matrix."""
    return [[1.0, 2.0], [3.0, 4.0]]


@pytest.fixture
def medium_matrix() -> List[List[float]]:
    """Provide a medium 10x10 test matrix."""
    return [[float(i * 10 + j) for j in range(10)] for i in range(10)]


@pytest.fixture
def large_matrix() -> List[List[float]]:
    """Provide a large 100x100 test matrix."""
    return [[float(i * 100 + j) for j in range(100)] for i in range(100)]


@pytest.fixture
def identity_matrix() -> List[List[float]]:
    """Provide a 3x3 identity matrix."""
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


@pytest.fixture
def zero_matrix() -> List[List[float]]:
    """Provide a 3x3 zero matrix."""
    return [[0.0, 0.0, 0.0] for _ in range(3)]


@pytest.fixture
def ragged_matrix() -> List[List[float]]:
    """Provide a ragged (invalid) matrix for error testing."""
    return [[1.0, 2.0], [3.0, 4.0, 5.0], [6.0]]


@pytest.fixture
def empty_matrix() -> List[List[float]]:
    """Provide an empty matrix for error testing."""
    return []


@pytest.fixture
def empty_row_matrix() -> List[List[float]]:
    """Provide a matrix with empty rows for error testing."""
    return [[]]


@pytest.fixture
def vector_1d() -> List[float]:
    """Provide a 1D vector for data transform tests."""
    return [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


@pytest.fixture
def vector_zeros() -> List[float]:
    """Provide a zero vector for normalization edge cases."""
    return [0.0, 0.0, 0.0, 0.0]


@pytest.fixture
def compute_engine():
    """Provide a ComputeEngine instance."""
    try:
        from forzium_engine import ComputeEngine
        return ComputeEngine()
    except ImportError:
        pytest.skip("Rust engine not available")


@pytest.fixture
def compute_request_schema():
    """Provide a ComputeRequestSchema instance."""
    try:
        from forzium_engine import ComputeRequestSchema
        return ComputeRequestSchema()
    except ImportError:
        pytest.skip("Rust engine not available")


@pytest.fixture
def pool_allocator():
    """Provide a PoolAllocator instance with 1MB capacity."""
    try:
        from forzium_engine import PoolAllocator
        return PoolAllocator(1024 * 1024)
    except ImportError:
        pytest.skip("Rust engine not available")


@pytest.fixture
def sample_compute_request() -> Dict[str, Any]:
    """Provide a valid compute request payload."""
    return {
        "data": [[1.0, 2.0], [3.0, 4.0]],
        "operation": "multiply",
        "parameters": {"factor": 2.0},
    }


@pytest.fixture
def invalid_compute_request() -> Dict[str, Any]:
    """Provide an invalid compute request payload (missing required fields)."""
    return {
        "data": [[1.0, 2.0], [3.0, 4.0]],
    }


# ============================================================================
# Benchmark fixtures
# ============================================================================

@pytest.fixture
def benchmark_matrix_sizes() -> List[int]:
    """Provide standard matrix sizes for benchmarking."""
    return [10, 50, 100, 200]


@pytest.fixture
def benchmark_iterations() -> int:
    """Return the number of benchmark iterations."""
    return int(os.environ.get("BENCHMARK_ITERATIONS", "100"))


# ============================================================================
# Platform detection fixtures
# ============================================================================

@pytest.fixture
def platform_info() -> Dict[str, Any]:
    """Provide platform information."""
    import platform
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "architecture": platform.architecture(),
    }


@pytest.fixture
def is_windows(platform_info: Dict[str, Any]) -> bool:
    """Check if running on Windows."""
    return platform_info["system"] == "Windows"


@pytest.fixture
def is_linux(platform_info: Dict[str, Any]) -> bool:
    """Check if running on Linux."""
    return platform_info["system"] == "Linux"


@pytest.fixture
def is_macos(platform_info: Dict[str, Any]) -> bool:
    """Check if running on macOS."""
    return platform_info["system"] == "Darwin"


# ============================================================================
# Memory profiling fixtures
# ============================================================================

@pytest.fixture
def memory_tracker():
    """Provide memory tracking utilities."""
    import tracemalloc
    
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()
    
    yield {
        "snapshot_before": snapshot_before,
        "get_current": lambda: tracemalloc.take_snapshot(),
        "get_diff": lambda: tracemalloc.take_snapshot().compare_to(
            snapshot_before, "lineno"
        ),
    }
    
    tracemalloc.stop()


# ============================================================================
# Test utilities
# ============================================================================

def assert_matrices_equal(
    a: List[List[float]],
    b: List[List[float]],
    rtol: float = 1e-9,
    atol: float = 1e-9,
) -> None:
    """
    Assert that two matrices are equal within tolerance.
    
    Args:
        a: First matrix
        b: Second matrix
        rtol: Relative tolerance
        atol: Absolute tolerance
    """
    assert len(a) == len(b), f"Row count mismatch: {len(a)} != {len(b)}"
    for i, (row_a, row_b) in enumerate(zip(a, b)):
        assert len(row_a) == len(row_b), f"Column count mismatch at row {i}"
        for j, (val_a, val_b) in enumerate(zip(row_a, row_b)):
            diff = abs(val_a - val_b)
            threshold = atol + rtol * abs(val_b)
            assert diff <= threshold, (
                f"Value mismatch at [{i}][{j}]: "
                f"{val_a} != {val_b} (diff={diff}, threshold={threshold})"
            )


def assert_vectors_equal(
    a: List[float],
    b: List[float],
    rtol: float = 1e-9,
    atol: float = 1e-9,
) -> None:
    """
    Assert that two vectors are equal within tolerance.
    
    Args:
        a: First vector
        b: Second vector
        rtol: Relative tolerance
        atol: Absolute tolerance
    """
    assert len(a) == len(b), f"Length mismatch: {len(a)} != {len(b)}"
    for i, (val_a, val_b) in enumerate(zip(a, b)):
        diff = abs(val_a - val_b)
        threshold = atol + rtol * abs(val_b)
        assert diff <= threshold, (
            f"Value mismatch at [{i}]: "
            f"{val_a} != {val_b} (diff={diff}, threshold={threshold})"
        )


# Export utilities for use in test modules
pytest.assert_matrices_equal = assert_matrices_equal
pytest.assert_vectors_equal = assert_vectors_equal


# ============================================================================
# Hooks
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Auto-mark tests based on their path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        
        # Auto-mark based on test name
        if "benchmark" in item.name:
            item.add_marker(pytest.mark.benchmark)
        if "memory" in item.name:
            item.add_marker(pytest.mark.memory)
        if "error" in item.name or "invalid" in item.name:
            item.add_marker(pytest.mark.error_handling)
