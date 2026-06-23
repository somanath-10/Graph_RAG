# Project workflows

This project is a GraphRAG MVP for patent PDFs. It has four moving parts:

- React/Vite frontend for ingestion, upload, questions, sources, and graph summary.
- FastAPI backend for API endpoints and orchestration.
- Qdrant for vector search over patent chunks.
- Neo4j for relationship/fact search over extracted graph data.

The current MVP rebuilds both Qdrant and Neo4j on every ingestion. Treat it as one active patent corpus at a time.

Most behavior is dynamic:

- Use `.env` for scalar values such as model names, ports, limits, token budgets, reset behavior, and file paths.
- Use `config/section_patterns.json` to change how patent sections are detected.
- Use `config/normalizer_replacements.json` to change chemical/text cleanup rules.
- Use `config/retrieval_terms.json` to change retrieval hints and keyword detection.
- Use `config/graph_schema.json` to change allowed entity and relationship labels.
- Use `backend/app/prompts/*.txt` to change extraction, context evaluation, and answer prompts.

## 1. Docker workflow

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY` in `.env`, or set `USE_MOCK_OPENAI=true` for local UI/backend testing without real OpenAI calls.
3. Run `docker compose up --build`.
4. Docker starts Qdrant, Neo4j, the FastAPI backend, and the Vite frontend using the ports configured in `.env`.
5. Open `http://localhost:5173`.
6. Click `Ingest included sample patent`.
7. Ask a question after ingestion finishes.

Useful URLs:

- Frontend: `http://localhost:5173`
- Backend docs: `http://localhost:8000/docs`
- Qdrant dashboard: `http://localhost:6333/dashboard`
- Neo4j browser: `http://localhost:7474`

## 2. Local development workflow

1. Start infrastructure only:

   ```bash
   docker compose up -d qdrant neo4j
   ```

2. Create and activate a Python virtual environment.

   Windows PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install backend dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and configure the OpenAI key or mock mode.
5. Run the backend:

   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. In another terminal, install and run the frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

7. Open `http://localhost:5173`.

## 3. Sample patent ingestion workflow

1. The frontend calls `POST /api/documents/ingest-sample`.
2. `backend/app/main.py` reads `RAW_DIR` and `SAMPLE_PDF_FILENAME` from settings and checks that the configured sample PDF exists.
3. `PatentGraphRAGPipeline.ingest_pdf()` starts the ingestion.
4. `pdf_loader.py` uses PyMuPDF to read every PDF page into `{page, text}` records.
5. `normalizer.py` uses `config/normalizer_replacements.json` to fix patent-style chemical markup and common formula encodings.
6. `chunker.py` uses `config/section_patterns.json` plus `.env` chunk size settings to detect sections and split text into chunks. The configured claim section is split around numbered claim boundaries where possible.
7. The pipeline writes normalized pages and chunks into `data/processed`.
8. `Embedder` sends chunk text to OpenAI embeddings, or creates deterministic mock embeddings when `USE_MOCK_OPENAI=true`.
9. If `RESET_VECTOR_STORE_ON_INGEST=true`, `QdrantStore.reset_collection()` deletes and recreates the configured collection. Otherwise it ensures the collection exists and upserts stable chunk IDs.
10. `QdrantStore.upsert_chunks()` stores each chunk payload plus its embedding vector.
11. `GraphExtractor` sends the first `MAX_GRAPH_CHUNKS` chunks to the OpenAI text model using the prompt files and graph schema configured in `.env` and `config/graph_schema.json`.
12. The pipeline writes the extracted graph JSON into `data/processed`.
13. If `RESET_GRAPH_STORE_ON_INGEST=true`, `Neo4jStore.reset()` deletes the old graph.
14. `Neo4jStore.upsert_graph()` merges extracted graph nodes and relationships.
15. The API returns document id, chunk count, entity count, relationship count, and a status message.
16. The frontend updates the status panel and refreshes the graph snapshot.

## 4. Uploaded PDF workflow

1. The user selects a PDF in the frontend.
2. The frontend sends `multipart/form-data` to `POST /api/documents/upload`.
3. The backend accepts only `.pdf` filenames and stores a sanitized filename under `data/raw`.
4. After saving the file, the backend runs the same ingestion pipeline as the sample patent workflow.
5. Existing Qdrant and Neo4j data are rebuilt for the uploaded patent.

## 5. Question answering workflow

1. The frontend sends `{question, top_k}` to `POST /api/query`. `top_k` comes from `VITE_QUERY_TOP_K`.
2. `PatentGraphRAGPipeline.answer()` creates a `HybridRetriever`.
3. The retriever embeds the question with the same embedding model used for chunks.
4. Qdrant returns the top matching chunks by vector similarity.
5. The retriever extracts formula-like and patent-specific terms from the question using `config/retrieval_terms.json`.
6. Neo4j searches graph relationships whose source, target, or evidence contains those terms, capped by `GRAPH_FACT_LIMIT`.
7. OpenAI evaluates candidate chunks with the configured context-evaluation prompt and marks which contexts should be kept.
8. `AnswerGenerator` builds a prompt from the kept chunks and graph facts using the configured answer prompt.
9. OpenAI generates the final answer, with instructions to avoid unsupported facts and preserve formulas exactly.
10. The backend returns the answer, source chunks, graph facts, and context evaluation details.
11. The frontend appends the answer to the chat panel and shows sources/facts on the right.

## 6. Graph snapshot workflow

1. The frontend calls `GET /api/graph?limit=...` using `VITE_GRAPH_LIMIT`.
2. `Neo4jStore.graph_snapshot()` reads up to the requested number of relationships, capped by `MAX_GRAPH_LIMIT`.
3. The backend converts graph nodes and edges into frontend-friendly JSON.
4. The UI displays node counts by type and a compact list of relationships.

## 7. Mock OpenAI workflow

Use mock mode when you want to verify the app without API cost or a key:

```text
USE_MOCK_OPENAI=true
```

In mock mode:

- Embeddings are deterministic local vectors.
- JSON extraction/evaluation returns empty graph/context structures.
- Final answers return a mock message.

Mock mode is useful for checking app wiring, Docker, upload handling, API health, Qdrant writes, and Neo4j resets. It does not produce real GraphRAG answers.

## 8. Verification workflow

Use these checks after changes:

```powershell
.\.venv\Scripts\python -m compileall backend scripts
.\.venv\Scripts\python -m pip check
cd frontend
npm run build
```

For runtime verification with mock mode:

```powershell
$env:USE_MOCK_OPENAI='true'
$env:QDRANT_URL='http://localhost:6333'
$env:NEO4J_URI='bolt://localhost:7687'
$env:NEO4J_USER='neo4j'
$env:NEO4J_PASSWORD='password'
.\.venv\Scripts\python scripts\run_ingest.py
```
