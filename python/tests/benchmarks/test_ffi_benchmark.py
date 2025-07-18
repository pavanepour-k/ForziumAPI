import pytest
import time
from forzium._rust import validate_buffer_size, validate_utf8_string

def test_ffi_call_overhead(benchmark):
    """MEASURE FFI call overhead."""
    data = b"x" * 1000

    def rust_validation():
        validate_buffer_size(data)
        validate_utf8_string(data)

    result = benchmark(rust_validation)

    # ASSERT overhead < 1μs per call
    assert benchmark.stats['mean'] < 0.000001

def test_large_data_transfer(benchmark):
    """MEASURE large data transfer performance."""
    data = b"x" * 1000000  # 1MB

    result = benchmark(validate_buffer_size, data)

    # ASSERT throughput > 1GB/s
    throughput_mbps = len(data) / benchmark.stats['mean'] / 1000000
    assert throughput_mbps > 1000
