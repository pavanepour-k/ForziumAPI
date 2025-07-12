from prometheus_client import Counter, Histogram, Gauge

ffi_calls_total = Counter(
    'ffi_calls_total',
    'Total FFI calls',
    ['function', 'status']
)

ffi_duration_seconds = Histogram(
    'ffi_duration_seconds',
    'FFI call duration',
    ['function']
)

memory_usage_bytes = Gauge(
    'memory_usage_bytes',
    'Current memory usage',
    ['component']
)
