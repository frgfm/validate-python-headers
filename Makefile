PYPROJECT_FILE = ./pyproject.toml

########################################################
# Code checks
########################################################


install-quality: ${PYPROJECT_FILE}
	uv sync --group quality
	uv run --group quality prek install

lint-check: ${PYPROJECT_FILE}
	uv run --group quality ruff format --check . --config ${PYPROJECT_FILE}
	uv run --group quality ruff check . --config ${PYPROJECT_FILE}

lint-format: ${PYPROJECT_FILE}
	uv run --group quality ruff check --fix . --config ${PYPROJECT_FILE}
	uv run --group quality ruff format . --config ${PYPROJECT_FILE}

prek: ${PYPROJECT_FILE} .pre-commit-config.yaml
	uv run --group quality prek run --all-files

typing-check: ${PYPROJECT_FILE}
	uv run --group quality ty check src

deps-check: .github/verify_deps_sync.py
	uv run --script .github/verify_deps_sync.py

# this target runs checks on all files
quality: lint-check typing-check deps-check

style: lint-format prek

########################################################
# Build
########################################################

lock: ${PYPROJECT_FILE}
	uv lock

lock-check: ${PYPROJECT_FILE}
	uv lock --check

# Run tests for the library
test:
	python -m unittest discover -s src/tests -v
