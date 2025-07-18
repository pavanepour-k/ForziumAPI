# Forzium Python Package

## Installation

```bash
cd python
poetry install
```

## Development

```bash
make install
make test
make coverage
make lint
make format
```

## Usage

```python
from forzium.validators import validate_buffer_size, validate_utf8_string, validate_u8_range

validate_buffer_size(b"data")
text = validate_utf8_string(b"Hello, world!")
value = validate_u8_range(42)
```

## Testing

```bash
poetry run pytest
poetry run pytest --cov=src --cov-report=term-missing
```

## Build

```bash
cd ../rust/bindings
maturin develop --release
```
