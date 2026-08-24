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

deps-check: .github/verify_deps_sync.py scripts/update_spdx_licenses.py
	uv run --script .github/verify_deps_sync.py
	uv run python scripts/update_spdx_licenses.py --check

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
	PYTHONOPTIMIZE=1 python -m unittest discover -s src/tests -v

package-check:
	uv build --clear --no-sources
	uv run --isolated --no-project --with dist/*.whl scripts/smoke_package.py
	uv run --isolated --no-project --with dist/*.tar.gz scripts/smoke_package.py
