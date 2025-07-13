.PHONY: all build test clean install format lint

all: build

build: build-rust build-python

build-rust:
	cd rust/core && cargo build --release
	cd rust/bindings && maturin develop --release

build-python:
	cd python && poetry install

test: test-rust test-python

test-rust:
	cd rust/core && cargo test
	cd rust/bindings && cargo test

test-python:
	cd python && poetry run pytest

coverage:
	cd rust/core && cargo tarpaulin --out Html
	cd python && poetry run pytest --cov=src --cov-report=html

clean:
	cd rust && cargo clean
	cd python && rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

install:
	cd python && poetry install --with dev
	pre-commit install

format:
	cd rust && cargo fmt
	cd python && poetry run black src tests

lint:
	cd rust && cargo clippy -- -D warnings
	cd python && poetry run ruff check src tests
	cd python && poetry run mypy src

validate-build-order:
	@echo "Validating build dependencies..."
	@test -f rust/core/Cargo.toml || (echo "ERROR: rust/core missing" && exit 1)
	@test -f rust/bindings/Cargo.toml || (echo "ERROR: rust/bindings missing" && exit 1)
	@test -f python/pyproject.toml || (echo "ERROR: python/pyproject.toml missing" && exit 1)