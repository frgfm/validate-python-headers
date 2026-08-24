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

spdx-check: scripts/update_spdx_licenses.py
	python scripts/update_spdx_licenses.py \
		--baseline-ref 94972478f38d080eadd37f098f771eb4cd235ae4 \
		--baseline-sha256 d557d74124ce6b367efd161e7b53ab1743ad45e302c3476bfb0988ee67b766e0 \
		--spdx-tag v3.28.0 \
		--expected-sha256 f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee \
		--check

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
