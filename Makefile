RUST_VERSION := 1.75.0
PYTHON_VERSION := 3.11
MATURIN_VERSION := 1.4.0

.PHONY: validate build test

validate:
	@rustc --version | grep -q $(RUST_VERSION) || (echo "RUST VERSION MISMATCH" && exit 1)

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
