# Patent Accuracy RAG with React + FastAPI

This is a runnable patent RAG comparison app. It builds one shared evidence layer from a patent PDF, then compares two retrieval engines:

- Evidence GraphRAG: shared exact/BM25/dense retrieval plus entity/relation evidence graph retrieval
- SproutRAG: shared exact/BM25/dense retrieval plus a sentence/paragraph/section hierarchy tree

It uses OpenAI for everything model-related:

- `gpt-5.4-mini` for entity extraction
- `gpt-5.4-mini` for final answer generation
- `text-embedding-3-small` for embeddings

Storage/UI/backend:

- React + Vite frontend
- FastAPI backend
- Qdrant vector database, with a local JSON vector fallback for development
- Neo4j graph database, with saved graph JSON fallback for development
- PyMuPDF PDF parsing

The project includes a sample patent PDF under `data/raw/`. Sample ingestion uses `SAMPLE_PDF_FILENAME` when set, otherwise it uses the first PDF in `RAW_DIR`.

## Architecture

```text
PDF
  -> PyMuPDF parser
  -> chemical formula normalizer
  -> section/claim/paragraph/sentence SourceUnits
  -> shared exact matcher + BM25 + dense vector index
  -> GraphRAG evidence chunks + OpenAI graph extraction + Neo4j/JSON graph
  -> SproutRAG hierarchy tree
  -> grounded answer generation with source_id citation validation
  -> side-by-side React comparison UI
```

## Quick start with Docker

Copy the environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your key:

```bash
OPENAI_API_KEY=your_key_here
```

For local use, change the default Neo4j password before the first run:

```bash
NEO4J_PASSWORD=choose_a_local_password
```

Start the complete stack:

```bash
docker compose up --build
```

Open:

```text
Frontend: http://localhost:5173
Backend API: http://localhost:8000/docs
Neo4j browser: http://localhost:7474
Qdrant: http://localhost:6333/dashboard
```

In the React app, click **Ingest included sample patent**.

Useful Docker commands:

```bash
docker compose ps
docker compose logs -f backend
docker compose down
docker compose down -v  # also deletes local Qdrant/Neo4j volumes
```

## Local development

Recommended local development uses Docker for Qdrant and Neo4j, and runs FastAPI/Vite directly on your machine.

Start local infrastructure:

```bash
docker compose up -d qdrant neo4j
```

Install backend:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env
```

On macOS/Linux, use `source .venv/bin/activate` instead of the PowerShell activation command.

Run backend:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Install and run frontend:

```bash
cd frontend
npm ci
VITE_API_URL=http://127.0.0.1:8000/api npm run dev
```

Ingest from CLI:

```bash
python scripts/run_ingest.py
```

The same flow is available from `make`:

```bash
make infra
make backend
make frontend
make smoke
```

If Docker/Qdrant/Neo4j are unavailable, you can still run a local mock stack:

```bash
USE_MOCK_OPENAI=true QDRANT_URL=http://127.0.0.1:1 NEO4J_URI=bolt://127.0.0.1:1 \
  uvicorn backend.app.main:app --host 127.0.0.1 --port 8010

cd frontend
VITE_API_URL=http://127.0.0.1:8010/api npm run dev -- --port 5177
```

For a detailed step-by-step explanation of each workflow, see `docs/WORKFLOWS.md`.

## Dynamic configuration

Operational behavior is controlled through `.env` and editable config files:

```text
.env                         scalar runtime values, paths, model names, limits, ports
config/section_patterns.json section names and regexes used by chunking
config/normalizer_replacements.json patent text and formula replacements
config/retrieval_terms.json retrieval hints and keyword terms
config/graph_schema.json allowed graph entity and relationship labels
backend/app/prompts/*.txt    LLM prompt templates
```

Change these files instead of editing Python/React code when you need different models, paths, prompt wording, chunk sizes, graph schema, retrieval hints, token budgets, or UI query defaults.

## API endpoints

```text
GET  /api/health
POST /api/documents/upload
POST /api/documents/{document_id}/index
POST /api/documents/ingest-sample
POST /api/query
POST /api/query/compare
GET  /api/graph
```

Example query request:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"document_id":"doc_abc123","question":"Summarize independent claim 1.","method":"graph","top_k":12}'
```

Example comparison request:

```bash
curl -X POST http://localhost:8000/api/query/compare \
  -H "Content-Type: application/json" \
  -d '{"document_id":"doc_abc123","question":"Which examples support claim 1?","top_k":12}'
```

## Notes

- Keep `OPENAI_SMALL_MODEL=gpt-5.4-mini` for low-cost extraction and answers.
- Keep `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` for low-cost embeddings.
- If you switch to `text-embedding-3-large`, change `EMBEDDING_DIMENSIONS` from `1536` to `3072`.
- Graph extraction is limited by `MAX_GRAPH_CHUNKS=25` to control cost. Increase it for larger patents.
- By default, each ingestion replaces vectors and graph nodes for the current document ID. Set `RESET_VECTOR_STORE_ON_INGEST=false` or `RESET_GRAPH_STORE_ON_INGEST=false` to append/update instead.

## Troubleshooting

If ingestion fails with connection errors, confirm:

```bash
docker compose ps
```

If the backend says OpenAI key is missing, check `.env`.

For UI-only testing without real OpenAI calls:

```bash
USE_MOCK_OPENAI=true
```

Real GraphRAG answers require `USE_MOCK_OPENAI=false` and a valid `OPENAI_API_KEY`.
