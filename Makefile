PYPROJECT_FILE = ./pyproject.toml
REQ_FILE = ./requirements.txt

########################################################
# Code checks
########################################################


install-quality: ${PYPROJECT_FILE}
	uv export --no-hashes --locked --only-dev -o ${REQ_FILE}
	uv pip install --system -r ${REQ_FILE}
	prek install

lint-check: ${PYPROJECT_FILE}
	ruff format --check . --config ${PYPROJECT_FILE}
	ruff check . --config ${PYPROJECT_FILE}

lint-format: ${PYPROJECT_FILE}
	ruff check --fix . --config ${PYPROJECT_FILE}
	ruff format . --config ${PYPROJECT_FILE}

prek: ${PYPROJECT_FILE} .pre-commit-config.yaml
	prek run --all-files

typing-check: ${PYPROJECT_FILE}
	ty check src

deps-check: .github/verify_deps_sync.py
	python .github/verify_deps_sync.py

# this target runs checks on all files
quality: lint-check typing-check deps-check

style: lint-format prek

########################################################
# Build
########################################################

lock: ${PYPROJECT_FILE}
	uv lock

# Run tests for the library
test:
	python -m unittest discover -s src/tests -v
