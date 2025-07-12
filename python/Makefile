PYTHON_VERSION := 3.11
POETRY_VERSION := 1.7.0

.PHONY: validate install test coverage lint format clean

validate:
	@echo "VALIDATING PYTHON VERSION..."
	@python --version | grep -q $(PYTHON_VERSION) || (echo "PYTHON VERSION MISMATCH" && exit 1)
	@echo "VALIDATING POETRY VERSION..."
	@poetry --version | grep -q $(POETRY_VERSION) || (echo "WARNING: POETRY VERSION MISMATCH")

install: validate
	@echo "INSTALLING DEPENDENCIES..."
	poetry install

test: install
	@echo "EXECUTING PYTHON TESTS..."
	poetry run pytest -xvs

coverage: install
	@echo "CHECKING TEST COVERAGE..."
	poetry run pytest --cov=src --cov-report=term-missing --cov-report=html
	@coverage=$$(poetry run pytest --cov=src --cov-report=term-missing | grep TOTAL | awk '{print $$4}' | sed 's/%//'); \
	if [ $${coverage%.*} -lt 90 ]; then \
		echo "COVERAGE $$coverage% < 90% REQUIREMENT"; \
		exit 1; \
	fi

lint: install
	@echo "RUNNING LINTERS..."
	poetry run ruff check src tests
	poetry run mypy src

format: install
	@echo "FORMATTING CODE..."
	poetry run black src tests
	poetry run ruff check --fix src tests

clean:
	@echo "CLEANING BUILD ARTIFACTS..."
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov .pytest_cache .mypy_cache .ruff_cache
