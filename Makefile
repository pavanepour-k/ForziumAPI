RUST_VERSION := 1.75.0
PYTHON_VERSION := 3.11
MATURIN_VERSION := 1.4.0

.PHONY: validate build test deploy clean

validate:
	@echo "VALIDATING RUST VERSION..."
	@rustc --version | grep -q $(RUST_VERSION) || (echo "RUST VERSION MISMATCH" && exit 1)
	@echo "VALIDATING PYTHON VERSION..."
	@python --version | grep -q $(PYTHON_VERSION) || (echo "PYTHON VERSION MISMATCH" && exit 1)

build: validate
	@echo "BUILDING RUST CORE..."
	cd rust/core && cargo build --release --locked
	@echo "BUILDING RUST BINDINGS..."
	cd rust/bindings && maturin build --release --strip
	@echo "INSTALLING PYTHON PACKAGE..."
	cd python && poetry install --no-dev

test: validate
	@echo "EXECUTING RUST TESTS..."
	cd rust && cargo test --all --release -- --test-threads=1
	@echo "EXECUTING PYTHON TESTS..."
	cd python && poetry run pytest -xvs
	@echo "EXECUTING INTEGRATION TESTS..."
	./scripts/integration_test.sh

deploy: test
	@echo "RUNNING SECURITY AUDIT..."
	cd rust && cargo audit --deny warnings
	cd python && poetry run pip-audit
	@echo "CHECKING LICENSES..."
	cd rust && cargo license --avoid-build-deps --avoid-dev-deps
	@echo "BUILDING RELEASE ARTIFACTS..."
	./scripts/build_release.sh

clean:
	cd rust && cargo clean
	cd python && rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov .pytest_cache



build-rust-core: validate
	cd rust/core && cargo build --release --locked

test-rust-core:
	cd rust/core && cargo test --all --release -- --test-threads=1
	cd rust/core && cargo tarpaulin --out Html --output-dir coverage

check-coverage:
	@coverage=$$(cargo tarpaulin --print-summary | grep "Coverage" | awk '{print $$2}' | sed 's/%//'); \
	if [ $${coverage%.*} -lt 90 ]; then \
		echo "COVERAGE $$coverage% < 90% REQUIREMENT"; \
		exit 1; \
	fi
