# Divi-Migrator Makefile

.PHONY: help install test lint format type-check clean build publish

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in development mode
	pip install -e ".[dev]"

install-dev:  ## Install with dev dependencies
	pip install -e ".[dev]"

test:  ## Run unit tests
	pytest tests/unit/ -v

test-integration:  ## Run integration tests (requires test WP site)
	pytest tests/integration/ -v --wp-url=$(WP_URL) --wp-user=$(WP_USER) --wp-pass=$(WP_PASS)

test-all:  ## Run all tests
	pytest tests/ -v

lint:  ## Run ruff linter
	ruff check .

lint-fix:  ## Run ruff linter with auto-fix
	ruff check --fix .

format:  ## Format code with ruff
	ruff format .

type-check:  ## Run mypy type checker
	mypy divi_migrator/

check: lint type-check  ## Run all checks (lint + type-check)

pre-commit-install:  ## Install pre-commit hooks
	pre-commit install

pre-commit-run:  ## Run pre-commit on all files
	pre-commit run --all-files

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage

build: clean  ## Build distribution packages
	python -m build

publish-test: build  ## Publish to TestPyPI
	twine upload --repository testpypi dist/*

publish: build  ## Publish to PyPI
	twine upload dist/*

dev-setup: install-dev pre-commit-install  ## Complete development setup

simulate:  ## Run offline end-to-end simulation + integrity scorecard (no live site)
	python -m divi_migrator.cli simulate --items 8

migrate-dry-run:  ## Run migration dry-run (requires env vars)
	divi-migrate migrate --type page --limit 5 --dry-run

migrate-pages:  ## Migrate pages (requires env vars)
	divi-migrate migrate --type page

migrate-posts:  ## Migrate posts (requires env vars)
	divi-migrate migrate --type post

clean-checkpoints:  ## Remove checkpoint files
	rm -f checkpoints/*.json