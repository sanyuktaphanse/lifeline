PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: evidence evidence-primary evidence-fallback evidence-swap dev

evidence:
	$(PYTHON) -m core.harness

# The live runs call a real provider and refuse to start without its key. LIVE_SCENARIO_LIMIT bounds them.
evidence-primary:
	$(PYTHON) -m core.harness --live primary

evidence-fallback:
	$(PYTHON) -m core.harness --live fallback

evidence-swap:
	$(PYTHON) -m core.harness --swap

dev:
	$(PYTHON) -m uvicorn --factory api.main:create_app --reload --host 127.0.0.1 --port 8000
