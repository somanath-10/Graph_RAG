from backend.app.config import get_settings
from backend.app.embedding.embedder import Embedder
from backend.app.shared_retrieval.evidence import to_evidence_item
from backend.app.storage.qdrant_store import QdrantStore


class DenseRetriever:
    def __init__(self):
        self.settings = get_settings()
        self.embedder = Embedder()
        self.qdrant = QdrantStore()

    def search(self, question: str, top_k: int | None = None, document_id: str | None = None) -> list[dict]:
        query_vector = self.embedder.embed_query(question)
        rows = self.qdrant.search(query_vector, top_k=top_k, document_id=document_id)
        return [to_evidence_item(row, 'dense', score=float(row.get('score', 0.0) or 0.0)) for row in rows]
