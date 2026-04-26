.PHONY: setup setup-separation setup-ml test lint serve smoke clean

PYTHON ?= python3.12
VENV ?= .venv
PIP := $(VENV)/bin/python -m pip
KTV := $(VENV)/bin/ktv

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -e ".[web,dev]"

setup-separation:
	$(PIP) install -e ".[web,dev,separation]"

setup-ml:
	$(PIP) install -e ".[web,dev,ml]"

test:
	$(VENV)/bin/python -m pytest -q

lint:
	$(VENV)/bin/python -m ruff check .

serve:
	$(KTV) --library library serve --host 127.0.0.1 --port 8000

smoke:
	$(KTV) import assets/朋友-周华健.mkv
	$(KTV) probe 朋友-周华健
	$(KTV) preview-tracks 朋友-周华健 --duration 5
	$(KTV) extract 朋友-周华健 --audio-index 0
	$(KTV) doctor 朋友-周华健

clean:
	rm -rf .pytest_cache .ruff_cache src/ktv_mux.egg-info
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
