PYTHON ?= python3
BACKEND_HOST ?= 0.0.0.0
BACKEND_PORT ?= 8000
FRONTEND_DIR ?= frontend
FRONTEND_PORT ?= 5173
API_BASE ?= http://localhost:$(BACKEND_PORT)/api

setup:
	$(PYTHON) -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

infra:
	docker compose up -d qdrant neo4j

infra-logs:
	docker compose logs -f qdrant neo4j

stack:
	docker compose up --build

stack-detached:
	docker compose up -d --build

down:
	docker compose down

down-volumes:
	docker compose down -v

backend:
	$(PYTHON) -m uvicorn backend.app.main:app --host $(BACKEND_HOST) --port $(BACKEND_PORT) --reload

frontend:
	cd $(FRONTEND_DIR) && npm ci && VITE_API_URL=$(API_BASE) npm run dev -- --port $(FRONTEND_PORT)

ingest:
	$(PYTHON) scripts/run_ingest.py

smoke:
	API_BASE=$(API_BASE) $(PYTHON) scripts/smoke_test.py
