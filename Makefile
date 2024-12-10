DOCKERFILE_PATH = ./Dockerfile
PYPROJECT_FILE = ./pyproject.toml
LOCK_FILE = ./uv.lock
REQ_FILE = ./requirements.txt
DOCKER_NAMESPACE ?= frgfm
DOCKER_REPO ?= validate-python-headers
DOCKER_TAG ?= latest

########################################################
# Code checks
########################################################


install-quality: ${PYPROJECT_FILE}
	uv export --no-hashes --locked --only-dev -o ${REQ_FILE}
	uv pip install --system -r ${REQ_FILE}
	pre-commit install

lint-check: ${PYPROJECT_FILE}
	ruff format --check . --config ${PYPROJECT_FILE}
	ruff check . --config ${PYPROJECT_FILE}

lint-format: ${PYPROJECT_FILE}
	ruff format . --config ${PYPROJECT_FILE}
	ruff check --fix . --config ${PYPROJECT_FILE}

precommit: ${PYPROJECT_FILE} .pre-commit-config.yaml
	pre-commit run --all-files

typing-check: ${PYPROJECT_FILE}
	mypy --config-file ${PYPROJECT_FILE}

deps-check: .github/verify_deps_sync.py
	python .github/verify_deps_sync.py

# this target runs checks on all files
quality: lint-check typing-check deps-check

style: lint-format precommit

########################################################
# Build
########################################################

lock: ${PYPROJECT_FILE}
	uv lock

req: ${PYPROJECT_FILE} ${LOCK_FILE}
	uv export --no-hashes --locked --no-dev -q -o ${REQ_FILE}

# Build the docker
build: req ${DOCKERFILE_PATH}
	docker build --platform linux/amd64 . -t ${DOCKER_NAMESPACE}/${DOCKER_REPO}:${DOCKER_TAG}

push: build
	docker push ${DOCKER_NAMESPACE}/${DOCKER_REPO}:${DOCKER_TAG}

# Run tests for the library
test: build
	docker run --workdir /github/workspace -v src:/github/workspace/src ${DOCKER_NAMESPACE}/${DOCKER_REPO}:${DOCKER_TAG} 'François-Guillaume Fernandez' 2022 Apache-2.0 src/ __init__.py .github/ ''
