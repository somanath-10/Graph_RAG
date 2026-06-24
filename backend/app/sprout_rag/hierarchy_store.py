from backend.app.storage.document_store import DocumentStore


class SproutHierarchyStore:
    def __init__(self):
        self.documents = DocumentStore()

    def save(self, document_id: str, nodes: list[dict]):
        self.documents.write_json(self.documents.sprout_path(document_id), nodes)

    def load(self, document_id: str) -> list[dict]:
        return self.documents.read_json(self.documents.sprout_path(document_id), default=[]) or []
