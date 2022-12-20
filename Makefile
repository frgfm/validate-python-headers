# this target runs checks on all files
quality:
	isort . -c
	flake8 ./
	mypy
	black --check .

# this target runs checks on all files and potentially modifies some of them
style:
	isort .
	black .

# Build the docker image
build:
	docker build . -t header-validator:py3.8.13-alpine

# Run tests for the library
test:
	docker build . -t header-validator:py3.8.13-alpine
	docker run --workdir /github/workspace -v src:/github/workspace/src header-validator:py3.8.13-alpine Apache-2.0 'François-Guillaume Fernandez' 2022 src/ __init__.py .github/
