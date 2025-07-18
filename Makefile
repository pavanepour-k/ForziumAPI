.PHONY: all build test clean install format lint coverage \
        build-rust build-python test-rust test-python \
        validate-build-order

all: build

build: build-rust build-python

build-rust:
	cargo build --workspace --release --manifest-path=rust/Cargo.toml
	cd rust/bindings && maturin develop --release

build-python:
	cd python && poetry install

test: test-rust test-python

test-rust:
	cargo test --workspace --manifest-path=rust/Cargo.toml
	cd rust/bindings && cargo test

test-python:
	cd python && poetry run pytest

coverage:
	cargo tarpaulin --manifest-path=rust/core/Cargo.toml --out Html
	cd python && poetry run pytest --cov=src --cov-report=html

clean:
	cargo clean --manifest-path=rust/Cargo.toml
	cd python && rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

install:
	cd python && poetry install --with dev
	pre-commit install

format:
	cargo fmt --manifest-path=rust/Cargo.toml
	cd python && poetry run black src tests

lint:
	cargo clippy --workspace --all-targets --all-features --manifest-path=rust/Cargo.toml -- -D warnings
	cd python && poetry run ruff check src tests
	cd python && poetry run mypy src

validate-build-order:
	@echo "Validating build dependencies..."
	@test -f rust/core/Cargo.toml || (echo "ERROR: rust/core missing" && exit 1)
	@test -f rust/bindings/Cargo.toml || (echo "ERROR: rust/bindings missing" && exit 1)
	@test -f python/pyproject.toml || (echo "ERROR: python/pyproject.toml missing" && exit 1)