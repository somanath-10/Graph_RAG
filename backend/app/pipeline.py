import hashlib
import json
from pathlib import Path
from time import perf_counter

from backend.app.config import get_settings
from backend.app.embedding.embedder import Embedder
from backend.app.extraction.graph_extractor import GraphExtractor
from backend.app.generation.answer_generator import AnswerGenerator
from backend.app.graph_rag.graph_chunk_builder import build_graph_evidence_chunks, validate_graph_evidence
from backend.app.graph_rag.graph_retriever import GraphRAGRetriever
from backend.app.ingest.chunker import document_id_from_path
from backend.app.ingest.normalizer import normalize_pages
from backend.app.ingest.pdf_loader import load_pdf_pages
from backend.app.ingest.source_units import build_source_units
from backend.app.sprout_rag.hierarchy_store import SproutHierarchyStore
from backend.app.sprout_rag.sprout_retriever import SproutRAGRetriever
from backend.app.sprout_rag.tree_builder import build_sprout_tree
from backend.app.storage.document_store import DocumentStore, now_iso
from backend.app.storage.neo4j_store import Neo4jStore
from backend.app.storage.qdrant_store import QdrantStore


class PatentGraphRAGPipeline:
    def __init__(self):
        self.settings = get_settings()
        Path(self.settings.processed_dir).mkdir(parents=True, exist_ok=True)
        Path(self.settings.index_dir).mkdir(parents=True, exist_ok=True)
        self.documents = DocumentStore()

    def ingest_pdf(self, pdf_path: str, mode: str = 'both') -> dict:
        return self.index_pdf(pdf_path, mode=mode)

    def index_pdf(self, pdf_path: str, mode: str = 'both') -> dict:
        mode = normalize_mode(mode)
        path = Path(pdf_path)
        document_id = document_id_from_path(path)
        pages = normalize_pages(load_pdf_pages(path), replacements=self.settings.normalizer_replacements)
        source_units = build_source_units(
            pages,
            document_id=document_id,
            section_patterns=self.settings.section_pattern_list,
        )
        if not source_units:
            raise ValueError('No source units could be built from this PDF.')

        metadata = self.documents.upsert_document({
            'document_id': document_id,
            'filename': path.name,
            'path': str(path),
            'page_count': len(pages),
            'sha256': sha256_file(path),
            'status': 'indexing',
            'updated_at': now_iso(),
        })

        self.documents.write_json(self.documents.pages_path(document_id), pages)
        self.documents.save_source_units(document_id, source_units)

        vector_units = self._vector_units(source_units)
        embedded = Embedder().embed_chunks(vector_units)
        qdrant = QdrantStore()
        qdrant.ensure_collection()
        if self.settings.reset_vector_store_on_ingest:
            qdrant.delete_document(document_id)
        qdrant.upsert_chunks(embedded)

        graph_entities = 0
        graph_relationships = 0
        graph_chunks = build_graph_evidence_chunks(source_units)
        self.documents.write_jsonl(self.documents.graph_chunks_path(document_id), graph_chunks)
        if mode in {'graph', 'both'}:
            graph = GraphExtractor().extract(graph_chunks, max_chunks=self.settings.max_graph_chunks)
            graph = validate_graph_evidence(graph, graph_chunks)
            self.documents.write_json(self.documents.graph_path(document_id), graph)
            graph_entities = len(graph.get('entities', []))
            graph_relationships = len(graph.get('relationships', []))
            neo4j = Neo4jStore()
            try:
                if self.settings.reset_graph_store_on_ingest:
                    neo4j.reset(document_id=document_id)
                neo4j.upsert_graph(graph)
            except Exception as exc:
                print(f'Neo4j unavailable; saved graph JSON fallback only: {exc}')
            finally:
                neo4j.close()
        else:
            graph = self.documents.read_json(self.documents.graph_path(document_id), default={}) or {}
            graph_entities = len(graph.get('entities', []))
            graph_relationships = len(graph.get('relationships', []))

        sprout_nodes = []
        if mode in {'sprout', 'both'}:
            sprout_nodes = build_sprout_tree(source_units, document_id=document_id)
            SproutHierarchyStore().save(document_id, sprout_nodes)
        else:
            sprout_nodes = SproutHierarchyStore().load(document_id)

        metadata.update({
            'status': 'indexed',
            'indexed_mode': mode,
            'source_units': len(source_units),
            'vector_units': len(vector_units),
            'graph_entities': graph_entities,
            'graph_relationships': graph_relationships,
            'sprout_nodes': len(sprout_nodes),
            'updated_at': now_iso(),
        })
        self.documents.upsert_document(metadata)

        return {
            'document_id': document_id,
            'filename': path.name,
            'status': 'indexed',
            'source_units': len(source_units),
            'vector_units': len(vector_units),
            'chunks': len(graph_chunks),
            'graph_entities': graph_entities,
            'graph_relationships': graph_relationships,
            'sprout_nodes': len(sprout_nodes),
            'message': f'Indexed {path.name} with {mode} mode from shared SourceUnits.',
        }

    def answer(
        self,
        question: str,
        top_k: int | None = None,
        document_id: str | None = None,
        method: str = 'graph',
    ) -> dict:
        method = normalize_method(method)
        document_id = self._resolve_document_id(document_id)
        source_units = self.documents.load_source_units(document_id)
        if not source_units:
            raise ValueError(f'No source units found for document_id={document_id}. Build indexes first.')

        started = perf_counter()
        if method == 'graph':
            retrieval = GraphRAGRetriever(source_units).retrieve(question, top_k=top_k, document_id=document_id)
        else:
            retrieval = SproutRAGRetriever(source_units, document_id=document_id).retrieve(question, top_k=top_k, document_id=document_id)
        answer = AnswerGenerator().generate_grounded(
            question,
            retrieval['evidence'],
            method=method,
            facts=retrieval.get('graph_facts', []),
        )
        latency_ms = (perf_counter() - started) * 1000
        sources = answer['sources']
        return {
            'document_id': document_id,
            'method': method,
            'answer': answer['answer'],
            'claims': answer['claims'],
            'sources': sources,
            'graph_facts': retrieval.get('graph_facts', []),
            'tree_path': retrieval.get('tree_path', []),
            'kept_contexts': self._kept_contexts(sources),
            'analysis': retrieval.get('analysis', {}),
            'can_answer': retrieval.get('can_answer', False),
            'insufficient_reason': retrieval.get('insufficient_reason'),
            'insufficient_evidence': answer['insufficient_evidence'],
            'citation_validation': answer['citation_validation'],
            'latency_ms': round(latency_ms, 2),
        }

    def _vector_units(self, source_units: list[dict]) -> list[dict]:
        allowed = set(self.settings.vector_source_unit_type_list)
        units = [unit for unit in source_units if unit.get('unit_type') in allowed]
        if not units:
            units = [unit for unit in source_units if unit.get('unit_type') != 'section']
        return [dict(unit, chunk_id=unit.get('source_id')) for unit in units]

    def _resolve_document_id(self, document_id: str | None) -> str:
        if document_id:
            return document_id
        latest = self.documents.latest_document()
        if not latest:
            raise ValueError('No indexed document found. Upload and index a patent first.')
        return latest['document_id']

    def _kept_contexts(self, sources: list[dict]) -> list[dict]:
        return [
            {
                'chunk_id': s.get('source_id'),
                'source_id': s.get('source_id'),
                'page': s.get('page_start'),
                'section': s.get('section'),
                'retrieval_channel': s.get('retrieval_channel'),
                'score': s.get('score'),
            }
            for s in sources
        ]

    def _write_json(self, filename: str, obj):
        path = Path(self.settings.processed_dir) / filename
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

    def _write_jsonl(self, filename: str, rows: list[dict]):
        path = Path(self.settings.processed_dir) / filename
        with path.open('w', encoding='utf-8') as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')


def normalize_mode(mode: str | None) -> str:
    mode = (mode or 'both').lower().strip()
    if mode not in {'graph', 'sprout', 'both'}:
        raise ValueError('mode must be one of: graph, sprout, both')
    return mode


def normalize_method(method: str | None) -> str:
    method = (method or 'graph').lower().strip()
    if method in {'graph_rag', 'graphrag'}:
        method = 'graph'
    if method in {'sprout_rag', 'sproutrag'}:
        method = 'sprout'
    if method not in {'graph', 'sprout'}:
        raise ValueError('method must be graph or sprout')
    return method


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()
