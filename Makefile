PYTHON ?= python3
BACKEND_HOST ?= 0.0.0.0
BACKEND_PORT ?= 8000
FRONTEND_DIR ?= frontend

setup:
	$(PYTHON) -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

infra:
	docker compose up -d qdrant neo4j

backend:
	$(PYTHON) -m uvicorn backend.app.main:app --host $(BACKEND_HOST) --port $(BACKEND_PORT) --reload

frontend:
	cd $(FRONTEND_DIR) && npm ci && npm run dev

ingest:
	$(PYTHON) scripts/run_ingest.py
