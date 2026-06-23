import json
from pathlib import Path

from backend.app.config import get_settings
from backend.app.ingest.pdf_loader import load_pdf_pages
from backend.app.ingest.normalizer import normalize_pages
from backend.app.ingest.chunker import chunk_pages, document_id_from_path
from backend.app.embedding.embedder import Embedder
from backend.app.extraction.graph_extractor import GraphExtractor
from backend.app.storage.qdrant_store import QdrantStore
from backend.app.storage.neo4j_store import Neo4jStore
from backend.app.retrieval.hybrid_retriever import HybridRetriever
from backend.app.generation.answer_generator import AnswerGenerator


class PatentGraphRAGPipeline:
    def __init__(self):
        self.settings = get_settings()
        Path(self.settings.processed_dir).mkdir(parents=True, exist_ok=True)

    def ingest_pdf(self, pdf_path: str) -> dict:
        document_id = document_id_from_path(pdf_path)
        pages = normalize_pages(load_pdf_pages(pdf_path), replacements=self.settings.normalizer_replacements)
        chunks = chunk_pages(
            pages,
            document_id=document_id,
            max_words=self.settings.chunk_max_words,
            overlap=self.settings.chunk_overlap_words,
            min_claim_words=self.settings.min_claim_words,
            claim_section=self.settings.claim_section_name,
            body_section=self.settings.body_section_name,
            section_patterns=self.settings.section_pattern_list,
            chunk_id_width=self.settings.chunk_id_width,
        )

        self._write_json(f'{document_id}_pages.json', pages)
        self._write_jsonl(f'{document_id}_chunks.jsonl', chunks)

        embedder = Embedder()
        embedded = embedder.embed_chunks(chunks)

        qdrant = QdrantStore()
        if self.settings.reset_vector_store_on_ingest:
            qdrant.reset_collection()
        else:
            qdrant.ensure_collection()
        qdrant.upsert_chunks(embedded)

        extractor = GraphExtractor()
        graph = extractor.extract(chunks, max_chunks=self.settings.max_graph_chunks)
        self._write_json(f'{document_id}_graph.json', graph)

        neo4j = Neo4jStore()
        try:
            if self.settings.reset_graph_store_on_ingest:
                neo4j.reset()
            neo4j.upsert_graph(graph)
        finally:
            neo4j.close()

        return {
            'document_id': document_id,
            'chunks': len(chunks),
            'graph_entities': len(graph.get('entities', [])),
            'graph_relationships': len(graph.get('relationships', [])),
            'message': 'Ingestion finished. Vector index and knowledge graph were rebuilt.'
        }

    def answer(self, question: str, top_k: int | None = None) -> dict:
        retriever = HybridRetriever()
        retrieval = retriever.retrieve(question, top_k=top_k)
        generator = AnswerGenerator()
        answer = generator.generate(question, retrieval['kept_contexts'], retrieval['graph_facts'])
        sources = []
        for c in retrieval['kept_contexts']:
            sources.append({
                'chunk_id': c.get('chunk_id'),
                'page_start': c.get('page_start'),
                'page_end': c.get('page_end'),
                'section': c.get('section'),
                'score': c.get('score'),
                'text': c.get('text'),
            })
        return {
            'answer': answer,
            'sources': sources,
            'graph_facts': retrieval['graph_facts'],
            'kept_contexts': [
                {
                    'chunk_id': c.get('chunk_id'),
                    'page': c.get('page_start'),
                    'section': c.get('section'),
                    'evaluation': c.get('evaluation', {}),
                }
                for c in retrieval['kept_contexts']
            ]
        }

    def _write_json(self, filename: str, obj):
        path = Path(self.settings.processed_dir) / filename
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

    def _write_jsonl(self, filename: str, rows: list[dict]):
        path = Path(self.settings.processed_dir) / filename
        with path.open('w', encoding='utf-8') as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
