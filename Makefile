PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: evidence

evidence:
	$(PYTHON) -m core.harness
