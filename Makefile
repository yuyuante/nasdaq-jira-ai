PYTHON ?= python

.PHONY: install lint format typecheck test check clean

install: ## Install the project and development dependencies.
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m playwright install chromium

lint: ## Run Ruff lint checks.
	$(PYTHON) -m ruff check .

format: ## Format Python files with Ruff and Black.
	$(PYTHON) -m ruff format .
	$(PYTHON) -m black .

typecheck: ## Run MyPy type checking.
	$(PYTHON) -m mypy src

test: ## Run the pytest test suite.
	$(PYTHON) -m pytest

check: ## Run all non-mutating quality checks and tests.
	$(MAKE) lint
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m black --check .
	$(MAKE) typecheck
	$(MAKE) test

clean: ## Remove Python caches, test artifacts, and build outputs.
	-rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	-find . -type d -name __pycache__ -prune -exec rm -rf {} +
	-find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete