# Patent GraphRAG with React + FastAPI + OpenAI Small Models

This is a complete runnable GraphRAG MVP for patent PDFs.

It uses OpenAI for everything model-related:

- `gpt-5.4-mini` for entity extraction
- `gpt-5.4-mini` for relationship extraction
- `gpt-5.4-mini` for context evaluation
- `gpt-5.4-mini` for final answer generation
- `text-embedding-3-small` for embeddings

Storage/UI/backend:

- React + Vite frontend
- FastAPI backend
- Qdrant vector database
- Neo4j graph database
- PyMuPDF PDF parsing

The project includes a sample patent PDF under `data/raw/`. Sample ingestion uses `SAMPLE_PDF_FILENAME` when set, otherwise it uses the first PDF in `RAW_DIR`.

## Architecture

```text
PDF
  -> PyMuPDF parser
  -> chemical formula normalizer
  -> section-aware chunker
  -> OpenAI embeddings
  -> Qdrant vector DB
  -> OpenAI graph extraction
  -> Neo4j knowledge graph
  -> hybrid retrieval
  -> OpenAI context evaluation
  -> OpenAI answer generation
  -> React UI
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

## Local development

Start Qdrant and Neo4j:

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
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Install and run frontend:

```bash
cd frontend
npm install
npm run dev
```

Ingest from CLI:

```bash
python scripts/run_ingest.py
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
POST /api/documents/ingest-sample
POST /api/documents/upload
POST /api/query
GET  /api/graph
```

Example query request:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Summarize independent claim 1.","top_k":12}'
```

## Notes

- Keep `OPENAI_SMALL_MODEL=gpt-5.4-mini` for low-cost extraction and answers.
- Keep `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` for low-cost embeddings.
- If you switch to `text-embedding-3-large`, change `EMBEDDING_DIMENSIONS` from `1536` to `3072`.
- Graph extraction is limited by `MAX_GRAPH_CHUNKS=25` to control cost. Increase it for larger patents.
- By default, each ingestion rebuilds the Qdrant collection and Neo4j graph. Set `RESET_VECTOR_STORE_ON_INGEST=false` or `RESET_GRAPH_STORE_ON_INGEST=false` to append/update instead.

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
