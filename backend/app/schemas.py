from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    page_count: int | None = None
    sha256: str | None = None


class IndexRequest(BaseModel):
    mode: Literal['graph', 'sprout', 'both'] = 'both'


class IngestResponse(BaseModel):
    document_id: str
    filename: str | None = None
    status: str = 'indexed'
    source_units: int = 0
    vector_units: int = 0
    chunks: int
    graph_entities: int = 0
    graph_relationships: int = 0
    sprout_nodes: int = 0
    message: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=4000)
    top_k: int | None = Field(default=None, ge=1)
    document_id: str = Field(..., min_length=1)
    method: Literal['graph', 'sprout'] = 'graph'


class SourceChunk(BaseModel):
    source_id: str | None = None
    chunk_id: str | None = None
    document_id: str | None = None
    unit_type: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    claim_number: int | None = None
    example_number: int | None = None
    retrieval_channel: str | None = None
    score: float | None = None
    text: str | None = None


class QueryResponse(BaseModel):
    document_id: str
    method: Literal['graph', 'sprout']
    answer: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[SourceChunk]
    graph_facts: list[dict[str, Any]] = Field(default_factory=list)
    tree_path: list[dict[str, Any]] = Field(default_factory=list)
    kept_contexts: list[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] = Field(default_factory=dict)
    can_answer: bool = False
    insufficient_reason: str | None = None
    insufficient_evidence: bool = False
    citation_validation: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float | None = None


class CompareRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=4000)
    top_k: int | None = Field(default=None, ge=1)
    document_id: str = Field(..., min_length=1)


class CompareResponse(BaseModel):
    graph_rag: QueryResponse
    sprout_rag: QueryResponse
    winner: Literal['graph_rag', 'sprout_rag', 'tie']
    reason: str
    graph_score: dict[str, Any]
    sprout_score: dict[str, Any]


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
