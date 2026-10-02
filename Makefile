PYPROJECT_FILE = ./pyproject.toml

.PHONY: docs docs-serve docs-cloudflare

install-quality: ${PYPROJECT_FILE}
	uv sync --group quality --no-install-project
	uv run --no-sync --group quality prek install

lint-check: quality-env ${PYPROJECT_FILE}
	cargo fmt --all --check
	uv run --no-sync --group quality ruff format --check . --config ${PYPROJECT_FILE}
	uv run --no-sync --group quality ruff check . --config ${PYPROJECT_FILE}

lint-format: quality-env ${PYPROJECT_FILE}
	cargo fmt --all
	uv run --no-sync --group quality ruff check --fix . --config ${PYPROJECT_FILE}
	uv run --no-sync --group quality ruff format . --config ${PYPROJECT_FILE}

prek: quality-env ${PYPROJECT_FILE} .pre-commit-config.yaml
	uv run --no-sync --group quality prek run --all-files

typing-check: quality-env ${PYPROJECT_FILE}
	cargo clippy --locked --all-targets -- -D warnings
	uv run --no-sync --group quality ty check src

deps-check: .github/verify_deps_sync.py
	uv run --script .github/verify_deps_sync.py

spdx-check: scripts/update_spdx_licenses.py
	uv run --no-project python scripts/update_spdx_licenses.py \
		--baseline-ref 94972478f38d080eadd37f098f771eb4cd235ae4 \
		--baseline-sha256 d557d74124ce6b367efd161e7b53ab1743ad45e302c3476bfb0988ee67b766e0 \
		--spdx-tag v3.28.0 \
		--expected-sha256 f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee \
		--check

quality: lint-check typing-check deps-check

headers-fix: Cargo.toml Cargo.lock ${PYPROJECT_FILE}
	cargo run --locked --quiet --bin lmh -- fix

quality-env:
	uv sync --group quality --no-install-project

style: lint-format prek

lock: ${PYPROJECT_FILE}
	uv lock

lock-check: ${PYPROJECT_FILE}
	uv lock --check

docs:
	uv run --locked --only-group docs zensical build --strict

docs-serve:
	uv run --locked --only-group docs zensical serve

docs-cloudflare: docs
	python .github/prepare_docs_assets.py

test:
	cargo test --locked
	PYTHONOPTIMIZE=1 uv run --no-project python -m unittest discover -s src/tests -v

package-check:
	uv build --clear --no-sources
	EXPECTED_VERSION="$$(uv version --short)" uv run --isolated --no-project --with dist/*.whl .github/smoke_distribution.py
	EXPECTED_VERSION="$$(uv version --short)" uv run --isolated --no-project --no-binary-package lint-my-headers --with dist/*.tar.gz .github/smoke_distribution.py
