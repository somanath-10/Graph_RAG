from pathlib import Path
import re
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.schemas import HealthResponse, IngestResponse, QueryRequest, QueryResponse, GraphResponse
from backend.app.pipeline import PatentGraphRAGPipeline
from backend.app.storage.neo4j_store import Neo4jStore

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def safe_pdf_filename(filename: str | None) -> str:
    name = Path(filename or '').name
    if not name.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail='Only PDF files are supported.')
    stem = re.sub(r'[^A-Za-z0-9_.-]+', '_', Path(name).stem).strip('._-')
    if not stem:
        stem = 'upload'
    return f'{stem}.pdf'


def bounded_limit(value: int | None, default: int, maximum: int) -> int:
    if value is None:
        value = default
    return max(1, min(value, maximum))


def configured_sample_pdf() -> Path:
    raw_dir = Path(settings.raw_dir)
    configured = (settings.sample_pdf_filename or '').strip()
    if configured:
        return raw_dir / configured
    pdfs = sorted(raw_dir.glob('*.pdf'))
    if not pdfs:
        raise HTTPException(status_code=404, detail=f'No sample PDF found in {raw_dir}')
    return pdfs[0]


@app.get('/api/health', response_model=HealthResponse)
def health():
    return HealthResponse(status='ok', app=settings.app_name)


@app.post('/api/documents/upload', response_model=IngestResponse)
async def upload_and_ingest(file: UploadFile = File(...)):
    filename = safe_pdf_filename(file.filename)
    raw_dir = Path(settings.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / filename
    with target.open('wb') as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = PatentGraphRAGPipeline().ingest_pdf(str(target))
        return IngestResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/documents/ingest-sample', response_model=IngestResponse)
def ingest_sample():
    sample = configured_sample_pdf()
    if not sample.exists():
        raise HTTPException(status_code=404, detail=f'Sample PDF not found at {sample}')
    try:
        result = PatentGraphRAGPipeline().ingest_pdf(str(sample))
        return IngestResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/query', response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        top_k = bounded_limit(req.top_k, settings.default_query_top_k, settings.max_query_top_k)
        result = PatentGraphRAGPipeline().answer(req.question, top_k=top_k)
        return QueryResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get('/api/graph', response_model=GraphResponse)
def graph_snapshot(limit: int | None = None):
    try:
        limit = bounded_limit(limit, settings.default_graph_limit, settings.max_graph_limit)
        store = Neo4jStore()
        try:
            data = store.graph_snapshot(limit=limit)
        finally:
            store.close()
        return GraphResponse(**data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
