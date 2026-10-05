PY ?= .venv/bin/python

.PHONY: setup lint test results results-offline corpus digest rc goldens space

setup:
	uv sync --extra dev

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

test:
	$(PY) -m pytest -q

# Network: verify FDA product codes and refresh the evaluation corpus (cached, rate limited).
corpus:
	$(PY) scripts/verify_product_codes.py
	$(PY) -m vigil corpus

# Everything that produces numbers for the README, from the committed corpus snapshot.
results-offline:
	$(PY) scripts/eval_tagger.py
	$(PY) scripts/run_mutants.py
	$(PY) scripts/traceability.py
	$(PY) scripts/render_results.py

results: corpus results-offline

digest:
	$(PY) -m vigil run

rc:
	$(PY) scripts/rc_gate.py

goldens:
	$(PY) scripts/make_goldens.py

space:
	$(PY) scripts/build_space.py
