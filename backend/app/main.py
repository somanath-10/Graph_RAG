import hashlib
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.app.comparison.compare_runner import CompareRunner
from backend.app.config import get_settings
from backend.app.ingest.pdf_loader import load_pdf_pages
from backend.app.pipeline import PatentAccuracyRAGPipeline
from backend.app.schemas import (
    CompareRequest,
    CompareResponse,
    DocumentUploadResponse,
    GraphResponse,
    HealthResponse,
    IndexRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)
from backend.app.storage.document_store import DocumentStore, now_iso
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


def require_api_key(request: Request):
    if not settings.api_key_required:
        return
    if not settings.api_key:
        raise HTTPException(status_code=503, detail='API key authentication is required but API_KEY is not configured.')
    x_api_key = request.headers.get(settings.api_key_header)
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail='Invalid or missing API key.')


@app.get('/api/health', response_model=HealthResponse)
def health():
    return HealthResponse(status='ok', app=settings.app_name)


@app.post('/api/documents/upload', response_model=DocumentUploadResponse, dependencies=[Depends(require_api_key)])
async def upload_document(file: UploadFile = File(...)):
    filename = safe_pdf_filename(file.filename)
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f'PDF exceeds max upload size of {settings.max_upload_bytes} bytes.')
    if not content.startswith(b'%PDF-'):
        raise HTTPException(status_code=400, detail='Uploaded file is not a valid PDF.')

    sha256 = hashlib.sha256(content).hexdigest()
    document_id = f'doc_{sha256[:16]}'
    raw_dir = Path(settings.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f'{document_id}_{filename}'
    target.write_bytes(content)

    try:
        page_count = len(load_pdf_pages(target))
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f'PDF could not be parsed: {exc}')

    DocumentStore().upsert_document({
        'document_id': document_id,
        'filename': filename,
        'path': str(target),
        'page_count': page_count,
        'sha256': sha256,
        'status': 'uploaded',
        'updated_at': now_iso(),
    })
    return DocumentUploadResponse(
        document_id=document_id,
        filename=filename,
        status='uploaded',
        page_count=page_count,
        sha256=sha256,
    )


@app.post('/api/documents/{document_id}/index', response_model=IngestResponse, dependencies=[Depends(require_api_key)])
def index_document(document_id: str, req: IndexRequest):
    doc = DocumentStore().get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f'Document not found: {document_id}')
    path = Path(doc.get('path') or '')
    if not path.exists():
        raise HTTPException(status_code=404, detail=f'PDF file not found for document_id={document_id}')
    try:
        return IngestResponse(**PatentAccuracyRAGPipeline().index_pdf(str(path), mode=req.mode))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/documents/ingest-sample', response_model=IngestResponse, dependencies=[Depends(require_api_key)])
def ingest_sample():
    sample = configured_sample_pdf()
    if not sample.exists():
        raise HTTPException(status_code=404, detail=f'Sample PDF not found at {sample}')
    try:
        return IngestResponse(**PatentAccuracyRAGPipeline().index_pdf(str(sample), mode='both'))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/query', response_model=QueryResponse, dependencies=[Depends(require_api_key)])
def query(req: QueryRequest):
    try:
        top_k = bounded_limit(req.top_k, settings.default_query_top_k, settings.max_query_top_k)
        result = PatentAccuracyRAGPipeline().answer(
            req.question,
            top_k=top_k,
            document_id=req.document_id,
            method=req.method,
        )
        return QueryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/query/compare', response_model=CompareResponse, dependencies=[Depends(require_api_key)])
def compare(req: CompareRequest):
    try:
        top_k = bounded_limit(req.top_k, settings.default_query_top_k, settings.max_query_top_k)
        result = CompareRunner().compare(req.question, document_id=req.document_id, top_k=top_k)
        return CompareResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get('/api/graph', response_model=GraphResponse, dependencies=[Depends(require_api_key)])
def graph_snapshot(limit: int | None = None, document_id: str | None = None):
    try:
        limit = bounded_limit(limit, settings.default_graph_limit, settings.max_graph_limit)
        store = Neo4jStore()
        try:
            data = store.graph_snapshot(limit=limit, document_id=document_id)
        finally:
            store.close()
        return GraphResponse(**data)
    except Exception as exc:
        data = graph_snapshot_from_json(document_id=document_id, limit=limit)
        if data is not None:
            return GraphResponse(**data)
        raise HTTPException(status_code=500, detail=str(exc))


def safe_pdf_filename(filename: str | None) -> str:
    name = Path(filename or '').name
    if not name.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail='Only PDF files are supported.')
    stem = ''.join(ch if ch.isalnum() or ch in {'_', '-', '.'} else '_' for ch in Path(name).stem).strip('._-')
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


def graph_snapshot_from_json(document_id: str | None, limit: int) -> dict | None:
    documents = DocumentStore()
    if not document_id:
        latest = documents.latest_document()
        document_id = (latest or {}).get('document_id')
    if not document_id:
        return {'nodes': [], 'edges': []}
    graph = documents.read_json(documents.graph_path(document_id), default=None)
    if graph is None:
        return {'nodes': [], 'edges': []}
    nodes = {}
    edges = []
    for rel in (graph.get('relationships', []) or [])[:limit]:
        source = str(rel.get('source') or '')
        target = str(rel.get('target') or '')
        if not source or not target:
            continue
        source_id = graph_fallback_node_id(source)
        target_id = graph_fallback_node_id(target)
        nodes[source_id] = {'id': source_id, 'name': source, 'type': 'Entity'}
        nodes[target_id] = {'id': target_id, 'name': target, 'type': 'Entity'}
        edges.append({
            'source': source_id,
            'target': target_id,
            'relation': rel.get('relation'),
            'evidence': rel.get('evidence'),
        })
    return {'nodes': list(nodes.values()), 'edges': edges}


def graph_fallback_node_id(name: str) -> str:
    digest = hashlib.sha1(name.strip().lower().encode('utf-8')).hexdigest()[:16]
    return f'entity:{digest}'
