from backend.app.graph_rag.graph_retriever import GraphRAGRetriever
from backend.app.storage.document_store import DocumentStore


class HybridRetriever:
    """Backward-compatible adapter for the GraphRAG retriever."""

    def __init__(self, document_id: str | None = None):
        self.documents = DocumentStore()
        latest = self.documents.latest_document()
        self.document_id = document_id or (latest or {}).get('document_id')
        self.source_units = self.documents.load_source_units(self.document_id) if self.document_id else []

    def retrieve(self, question: str, top_k: int | None = None) -> dict:
        result = GraphRAGRetriever(self.source_units).retrieve(question, top_k=top_k, document_id=self.document_id)
        return {
            'chunks': result['evidence'],
            'graph_facts': result['graph_facts'],
            'kept_contexts': result['evidence'],
            'terms': [],
        }
