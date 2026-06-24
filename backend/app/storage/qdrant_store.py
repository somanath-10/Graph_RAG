from uuid import NAMESPACE_URL, uuid5
import json
import math
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, FilterSelector, MatchValue, PointStruct, VectorParams

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
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection not in existing:
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self.settings.embedding_dimensions, distance=self._distance()),
                )
        except Exception:
            self._local_path().parent.mkdir(parents=True, exist_ok=True)
            if not self._local_path().exists():
                self._local_write([])

    def reset_collection(self):
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection in existing:
                self.client.delete_collection(self.collection)
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.settings.embedding_dimensions, distance=self._distance()),
            )
        except Exception:
            self._local_path().parent.mkdir(parents=True, exist_ok=True)
            self._local_write([])

    def delete_document(self, document_id: str):
        query_filter = Filter(
            must=[FieldCondition(key='document_id', match=MatchValue(value=document_id))]
        )
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection not in existing:
                self.ensure_collection()
                return
            self.client.delete(
                collection_name=self.collection,
                points_selector=FilterSelector(filter=query_filter),
            )
        except Exception:
            rows = [
                row for row in self._local_load()
                if (row.get('payload') or {}).get('document_id') != document_id
            ]
            self._local_write(rows)

    def upsert_chunks(self, embedded_chunks: list[dict]):
        points = []
        for idx, item in enumerate(embedded_chunks):
            payload = {k: v for k, v in item.items() if k != 'embedding'}
            point_key = item.get('source_id') or item.get('chunk_id') or f'{self.collection}:{idx}'
            points.append(PointStruct(id=str(uuid5(NAMESPACE_URL, point_key)), vector=item['embedding'], payload=payload))
        if points:
            try:
                self.client.upsert(collection_name=self.collection, points=points)
            except Exception:
                self._local_upsert(embedded_chunks)

    def search(self, query_vector: list[float], top_k: int | None = None, document_id: str | None = None) -> list[dict]:
        top_k = top_k or self.settings.default_query_top_k
        query_filter = None
        if document_id:
            query_filter = Filter(
                must=[FieldCondition(key='document_id', match=MatchValue(value=document_id))]
            )
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection not in existing:
                return self._local_search(query_vector, top_k=top_k, document_id=document_id)
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
        except Exception:
            return self._local_search(query_vector, top_k=top_k, document_id=document_id)
        out = []
        for r in results:
            payload = dict(r.payload or {})
            payload['score'] = float(r.score)
            out.append(payload)
        return out

    def _local_path(self) -> Path:
        return Path(self.settings.index_dir) / f'{self.collection}_vectors.json'

    def _local_load(self) -> list[dict]:
        path = self._local_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _local_write(self, rows: list[dict]):
        path = self._local_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')

    def _local_upsert(self, embedded_chunks: list[dict]):
        existing = {row['id']: row for row in self._local_load() if row.get('id')}
        for idx, item in enumerate(embedded_chunks):
            point_key = item.get('source_id') or item.get('chunk_id') or f'{self.collection}:{idx}'
            point_id = str(uuid5(NAMESPACE_URL, point_key))
            payload = {k: v for k, v in item.items() if k != 'embedding'}
            existing[point_id] = {'id': point_id, 'vector': item.get('embedding') or [], 'payload': payload}
        self._local_write(list(existing.values()))

    def _local_search(self, query_vector: list[float], top_k: int, document_id: str | None = None) -> list[dict]:
        scored = []
        for row in self._local_load():
            payload = dict(row.get('payload') or {})
            if document_id and payload.get('document_id') != document_id:
                continue
            score = cosine_similarity(query_vector, row.get('vector') or [])
            payload['score'] = score
            scored.append(payload)
        scored.sort(key=lambda item: item.get('score', 0.0), reverse=True)
        return scored[:top_k]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(size))
    norm_a = math.sqrt(sum(a[i] * a[i] for i in range(size)))
    norm_b = math.sqrt(sum(b[i] * b[i] for i in range(size)))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)
