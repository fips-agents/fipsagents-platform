.PHONY: venv install dev run test lint clean container

PYTHON ?= python3
VENV ?= .venv
PORT ?= 8080

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip

install: venv
	$(VENV)/bin/pip install -e .

dev: venv
	$(VENV)/bin/pip install -e ".[dev,postgres]"

run:
	PLATFORM_BACKEND=sqlite \
	PLATFORM_AUTH_MODE=none \
	$(VENV)/bin/uvicorn fipsagents_platform.app:app --host 127.0.0.1 --port $(PORT) --reload

test:
	$(VENV)/bin/pytest -v

lint:
	$(VENV)/bin/python -m compileall -q src

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .coverage htmlcov
	find . -name __pycache__ -type d -exec rm -rf {} +
	rm -f *.db *.db-shm *.db-wal

container:
	podman build --platform linux/amd64 -t fipsagents-platform:dev -f Containerfile .
