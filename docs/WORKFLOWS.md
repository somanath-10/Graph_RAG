# Project workflows

This project is a dual-engine Patent Accuracy RAG system for patent PDFs. It compares Evidence GraphRAG and SproutRAG retrieval over the same shared document evidence layer.

The main moving parts are:

- React/Vite frontend for ingestion, upload, questions, comparison, sources, and graph summary.
- FastAPI backend for API endpoints and orchestration.
- Shared SourceUnits for fair GraphRAG/SproutRAG comparison.
- Shared exact matching and BM25 retrieval over SourceUnits.
- Qdrant for vector search over vector-eligible SourceUnits.
- Neo4j for relationship/fact search over extracted graph data.
- Sprout hierarchy storage for tree-based long-document retrieval.

Each ingestion builds a document-scoped evidence layer. By default, existing vectors and graph nodes for the same document ID are replaced, while other indexed documents are left in place.

Important architecture rule: GraphRAG and SproutRAG must start from the same SourceUnits. The project should not use separate GraphRAG-specific and SproutRAG-specific parsers/chunkers, because that would make the comparison unfair. Graph facts and Sprout parent summaries are retrieval helpers, not final evidence. Final citations must always point to original SourceUnits.

The high-level flow is:

```text
Patent PDF
  -> shared SourceUnits
  -> shared exact/BM25/vector retrieval
  -> Evidence GraphRAG graph index
  -> SproutRAG hierarchy tree
  -> GraphRAG answer
  -> SproutRAG answer
  -> comparison result
```

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
3. `PatentAccuracyRAGPipeline.ingest_pdf()` starts the ingestion.
4. `pdf_loader.py` uses PyMuPDF to read every PDF page into `{page, text}` records.
5. `normalizer.py` uses `config/normalizer_replacements.json` to fix patent-style chemical markup and common formula encodings.
6. `source_units.py` uses `config/section_patterns.json` to build section, claim, example, paragraph, and sentence SourceUnits with stable `source_id` citations.
7. The pipeline writes normalized pages and SourceUnits into `data/processed`.
8. Shared retrieval assets are prepared:
   - `ExactMatcher` and `BM25Retriever` read the same SourceUnits at query time.
   - `Embedder` sends vector-eligible SourceUnits to OpenAI embeddings, or creates deterministic mock embeddings when `USE_MOCK_OPENAI=true`.
   - `QdrantStore.upsert_chunks()` stores each vector SourceUnit payload plus its embedding vector.
9. If `RESET_VECTOR_STORE_ON_INGEST=true`, `QdrantStore.delete_document()` removes existing vectors for the current document ID before upsert. The collection itself is preserved.
10. The GraphRAG index is built:
   - `build_graph_evidence_chunks()` converts SourceUnits into graph evidence chunks.
   - `GraphExtractor` sends the first `MAX_GRAPH_CHUNKS` graph evidence chunks to the OpenAI text model.
   - `validate_graph_evidence()` keeps graph facts grounded in extracted evidence.
   - The extracted graph JSON is written into `data/processed`.
   - If `RESET_GRAPH_STORE_ON_INGEST=true`, `Neo4jStore.reset(document_id=...)` deletes existing graph nodes for the current document ID.
   - `Neo4jStore.upsert_graph()` merges extracted graph nodes and relationships.
11. The SproutRAG index is built:
   - `build_sprout_tree()` creates document, section, claim, example, paragraph, and sentence nodes.
   - `rollup_text()` creates parent retrieval text from child/source text.
   - `SproutHierarchyStore` stores the hierarchy under `INDEX_DIR`.
   - `SproutBeamSearch` indexes/scores Sprout node text at retrieval time.
   - Dense vector search still uses the shared SourceUnit embeddings in Qdrant, so final citations remain SourceUnit-based.
12. The API returns document id, SourceUnit count, vector unit count, graph evidence chunk count, entity count, relationship count, Sprout node count, and a status message.
13. The frontend updates the status panel and refreshes the graph snapshot.

## 4. Uploaded PDF workflow

1. The user selects a PDF in the frontend.
2. The frontend sends `multipart/form-data` to `POST /api/documents/upload`.
3. The backend accepts only `.pdf` filenames and stores a sanitized filename under `data/raw`.
4. After saving the file, the backend runs the same ingestion pipeline as the sample patent workflow.
5. Existing Qdrant and Neo4j data for the uploaded patent document ID are replaced according to the reset flags.

## 5. SproutRAG indexing workflow

1. After SourceUnits are created, `build_sprout_tree()` reads section, claim, example, paragraph, and sentence SourceUnits.
2. Sentence SourceUnits become leaf nodes.
3. Paragraph, claim, and example SourceUnits become intermediate evidence nodes.
4. Section nodes group the paragraph, claim, example, and sentence nodes attached to each section.
5. A document/root node groups all section nodes.
6. Each Sprout node stores:
   - `node_id`
   - `document_id`
   - `level`
   - `parent_id`
   - `child_ids`
   - `source_unit_ids`
   - `page_start`
   - `page_end`
   - `section`
   - `text`
7. `rollup_text()` fills empty parent text from child/source text so hierarchy search can score broader context.
8. `SproutHierarchyStore.save()` persists the node list for the document.
9. During retrieval, `SproutBeamSearch` indexes/scores hierarchy node text and returns source-linked candidates.
10. Dense retrieval for SproutRAG uses the shared Qdrant SourceUnit embeddings, not separate final-evidence nodes.
11. If Sprout node embeddings are added later, each embedded node must preserve `source_unit_ids` and must resolve final citations back to original SourceUnits.
12. Sprout hierarchy text and parent summaries are retrieval helpers, not final evidence. Final answer citations must point back to original SourceUnits.

## 6. Question answering workflow

1. The frontend sends `{document_id, question, top_k, method}` to `POST /api/query`. `top_k` comes from `VITE_QUERY_TOP_K`.
2. `PatentAccuracyRAGPipeline.answer()` creates either `GraphRAGRetriever` or `SproutRAGRetriever`.
3. Both retrievers use the shared exact matcher, BM25 retriever, and Qdrant vector retriever over the same SourceUnits.
4. GraphRAG also extracts formula-like and patent-specific terms from the question using `config/retrieval_terms.json`.
5. GraphRAG searches Neo4j, or the saved graph JSON fallback, for relationships whose source, target, or evidence contains those terms, capped by `GRAPH_FACT_LIMIT`.
6. SproutRAG also searches the stored hierarchy tree with `SproutBeamSearch`.
7. Retrieval results are fused/ranked into answer evidence.
8. OpenAI evaluates candidate SourceUnits with the configured context-evaluation prompt and marks which contexts should be kept.
9. `AnswerGenerator` builds a prompt from the kept SourceUnits and graph facts using the configured answer prompt.
10. OpenAI generates the final answer, with instructions to avoid unsupported facts and preserve formulas exactly.
11. The citation validator checks whether generated citations match returned SourceUnits.
12. The backend returns the answer, source citations, graph facts or tree path, citation validation, and context evaluation details.
13. The frontend appends the answer to the chat panel and shows sources/facts/tree path on the right.

Supported logical modes are:

- `graph`: call `POST /api/query` with `"method": "graph"`.
- `sprout`: call `POST /api/query` with `"method": "sprout"`.
- `compare`: call `POST /api/query/compare`.

Example single-engine request:

```json
{
  "document_id": "doc_abc123",
  "question": "Which examples support claim 1?",
  "top_k": 10,
  "method": "graph"
}
```

## 7. Compare workflow

1. The frontend sends `{document_id, question, top_k}` to `POST /api/query/compare`.
2. The backend runs GraphRAG retrieval:
   - exact matcher
   - BM25
   - vector search
   - graph search
   - fusion/ranking
3. The backend runs SproutRAG retrieval:
   - exact matcher
   - BM25
   - vector search
   - hierarchy/tree search
   - fusion/ranking
4. The shared answer generator creates one grounded answer for GraphRAG evidence.
5. The shared answer generator creates one grounded answer for SproutRAG evidence.
6. The citation validator checks both answers.
7. The comparison engine scores:
   - citation precision
   - capped evidence count as a supporting signal
   - retrieval channel diversity
   - unsupported claim count
   - latency
8. Citation quality and unsupported-claim penalties carry more weight than raw evidence count, so a long source list cannot beat a better-cited answer by volume alone.
9. The backend returns both answers, both source lists, scores, a winner, and a winner explanation.
10. The frontend displays the answers side by side.

Example compare request:

```json
{
  "document_id": "doc_abc123",
  "question": "Which examples support claim 1?",
  "top_k": 10
}
```

Current compare response shape:

```json
{
  "graph_rag": {
    "document_id": "doc_abc123",
    "method": "graph",
    "answer": "...",
    "sources": [],
    "graph_facts": [],
    "tree_path": [],
    "citation_validation": {
      "citation_precision": 1.0,
      "unsupported_claim_count": 0
    },
    "latency_ms": 2400
  },
  "sprout_rag": {
    "document_id": "doc_abc123",
    "method": "sprout",
    "answer": "...",
    "sources": [],
    "graph_facts": [],
    "tree_path": [],
    "citation_validation": {
      "citation_precision": 1.0,
      "unsupported_claim_count": 1
    },
    "latency_ms": 1900
  },
  "winner": "graph_rag",
  "reason": "GraphRAG retrieved stronger cited evidence with graph-linked support.",
  "graph_score": {
    "score": 88.8,
    "citation_precision": 1.0,
    "evidence_count": 8,
    "retrieval_channels": ["bm25", "dense", "graph"],
    "unsupported_claim_count": 0,
    "latency_ms": 2400
  },
  "sprout_score": {
    "score": 74.1,
    "citation_precision": 1.0,
    "evidence_count": 8,
    "retrieval_channels": ["bm25", "dense", "sprout_tree"],
    "unsupported_claim_count": 1,
    "latency_ms": 1900
  }
}
```

## 8. Graph snapshot workflow

1. The frontend calls `GET /api/graph?limit=...` using `VITE_GRAPH_LIMIT`.
2. `Neo4jStore.graph_snapshot()` reads up to the requested number of relationships, capped by `MAX_GRAPH_LIMIT`.
3. The backend converts graph nodes and edges into frontend-friendly JSON.
4. The UI displays node counts by type and a compact list of relationships.

## 9. Mock OpenAI workflow

Use mock mode when you want to verify the app without API cost or a key:

```text
USE_MOCK_OPENAI=true
```

In mock mode:

- Embeddings are deterministic local vectors.
- JSON extraction/evaluation returns empty graph/context structures.
- Final answers return a mock message.

Mock mode is useful for checking app wiring, Docker, upload handling, API health, Qdrant writes, Neo4j fallback behavior, and Sprout hierarchy creation. It does not produce real GraphRAG/SproutRAG answers.

## 10. Verification workflow

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
