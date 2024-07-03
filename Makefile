# this target runs checks on all files
quality:
	ruff format --check .
	ruff check .
	mypy

# this target runs checks on all files and potentially modifies some of them
style:
	ruff format .
	ruff check --fix .

# Pin the dependencies
lock:
	poetry lock --no-update

# Build the docker image
build:
	docker build . -t header-validator:latest

# Run tests for the library
test:
	docker build . -t header-validator:latest
	docker run --workdir /github/workspace -v src:/github/workspace/src header-validator:latest 'François-Guillaume Fernandez' 2022 Apache-2.0 src/ __init__.py .github/ ''
