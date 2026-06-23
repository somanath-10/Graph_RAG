from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from backend.app.config import get_settings


class QdrantStore:
    def __init__(self):
        self.settings = get_settings()
        self.client = QdrantClient(url=self.settings.qdrant_url)
        self.collection = self.settings.qdrant_collection

    def _distance(self) -> Distance:
        distance_name = self.settings.qdrant_distance.upper()
        try:
            return getattr(Distance, distance_name)
        except AttributeError as exc:
            supported = ', '.join(item.name for item in Distance)
            raise ValueError(f'Unsupported QDRANT_DISTANCE={self.settings.qdrant_distance}. Use one of: {supported}') from exc

    def ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.settings.embedding_dimensions, distance=self._distance()),
            )

    def reset_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection in existing:
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=self.settings.embedding_dimensions, distance=self._distance()),
        )

    def upsert_chunks(self, embedded_chunks: list[dict]):
        points = []
        for idx, item in enumerate(embedded_chunks):
            payload = {k: v for k, v in item.items() if k != 'embedding'}
            point_key = item.get('chunk_id') or f'{self.collection}:{idx}'
            points.append(PointStruct(id=str(uuid5(NAMESPACE_URL, point_key)), vector=item['embedding'], payload=payload))
        if points:
            self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query_vector: list[float], top_k: int | None = None) -> list[dict]:
        top_k = top_k or self.settings.default_query_top_k
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        out = []
        for r in results:
            payload = dict(r.payload or {})
            payload['score'] = float(r.score)
            out.append(payload)
        return out
