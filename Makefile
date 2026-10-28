PY := backend/.venv/Scripts/python
# On Linux/macOS use: PY := backend/.venv/bin/python

.PHONY: setup dev seed eval test shots

setup:
	python -m venv backend/.venv
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm install

dev:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000 & cd frontend && npm run dev

# generates the synthetic dataset, loads the DB and runs the pipeline on every application (~5 min on CPU)
seed:
	$(PY) -m data.generator.seed --seed 42

eval:
	$(PY) eval/evaluate.py

test:
	cd backend && ../$(PY) -m pytest -q

shots:
	cd frontend && node scripts/demo_shots.mjs
