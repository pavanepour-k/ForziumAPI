from prometheus_client import Counter, Histogram

ffi_calls_total = Counter(
    'forzium_ffi_calls_total',
    'Total FFI calls to Rust functions',
    ['function', 'status']
)

ffi_duration_seconds = Histogram(
    'forzium_ffi_duration_seconds',
    'FFI call duration in seconds',
    ['function']
)

__all__ = ['ffi_calls_total', 'ffi_duration_seconds']