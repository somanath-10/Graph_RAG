import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.config import get_settings


class DocumentStore:
    def __init__(self):
        self.settings = get_settings()
        self.processed_dir = Path(self.settings.processed_dir)
        self.index_dir = Path(self.settings.index_dir)
        self.registry_path = Path(self.settings.document_registry_path)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def upsert_document(self, metadata: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(metadata)
        metadata.setdefault('updated_at', now_iso())
        docs = self._read_registry()
        docs[metadata['document_id']] = {**docs.get(metadata['document_id'], {}), **metadata}
        self._write_registry(docs)
        return docs[metadata['document_id']]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        return self._read_registry().get(document_id)

    def latest_document(self) -> dict[str, Any] | None:
        docs = list(self._read_registry().values())
        if not docs:
            return None
        return sorted(docs, key=lambda item: item.get('updated_at', ''), reverse=True)[0]

    def source_units_path(self, document_id: str) -> Path:
        return self.processed_dir / f'{document_id}_source_units.json'

    def pages_path(self, document_id: str) -> Path:
        return self.processed_dir / f'{document_id}_pages.json'

    def graph_path(self, document_id: str) -> Path:
        return self.processed_dir / f'{document_id}_graph.json'

    def graph_chunks_path(self, document_id: str) -> Path:
        return self.processed_dir / f'{document_id}_graph_chunks.jsonl'

    def sprout_path(self, document_id: str) -> Path:
        return self.index_dir / document_id / self.settings.sprout_store_filename

    def write_json(self, path: Path, obj: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

    def read_json(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return default

    def write_jsonl(self, path: Path, rows: list[dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

    def load_source_units(self, document_id: str) -> list[dict]:
        return self.read_json(self.source_units_path(document_id), default=[]) or []

    def save_source_units(self, document_id: str, source_units: list[dict]):
        self.write_json(self.source_units_path(document_id), source_units)

    def _read_registry(self) -> dict[str, dict[str, Any]]:
        if not self.registry_path.exists():
            return {}
        try:
            data = json.loads(self.registry_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _write_registry(self, docs: dict[str, dict[str, Any]]):
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(docs, indent=2, ensure_ascii=False), encoding='utf-8')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
