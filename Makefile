PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: evidence dev

evidence:
	$(PYTHON) -m core.harness

dev:
	$(PYTHON) -m uvicorn --factory api.main:create_app --reload --port 8000
