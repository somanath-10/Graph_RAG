from pydantic import BaseModel, Field
from typing import Any


class HealthResponse(BaseModel):
    status: str
    app: str


class IngestResponse(BaseModel):
    document_id: str
    chunks: int
    graph_entities: int = 0
    graph_relationships: int = 0
    message: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2)
    top_k: int | None = Field(default=None, ge=1)


class SourceChunk(BaseModel):
    chunk_id: str
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    score: float | None = None
    text: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    graph_facts: list[dict[str, Any]]
    kept_contexts: list[dict[str, Any]] = []


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
