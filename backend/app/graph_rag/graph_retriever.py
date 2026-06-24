from backend.app.config import get_settings
from backend.app.shared_retrieval.bm25_retriever import BM25Retriever
from backend.app.shared_retrieval.dense_retriever import DenseRetriever
from backend.app.shared_retrieval.evidence import dedupe_evidence
from backend.app.shared_retrieval.evidence import to_evidence_item
from backend.app.shared_retrieval.exact_matcher import ExactMatcher
from backend.app.shared_retrieval.fusion import reciprocal_rank_fusion
from backend.app.shared_retrieval.query_analyzer import analyze_query
from backend.app.storage.document_store import DocumentStore
from backend.app.storage.neo4j_store import Neo4jStore


class GraphRAGRetriever:
    def __init__(self, source_units: list[dict]):
        self.settings = get_settings()
        self.source_units = source_units

    def retrieve(self, question: str, top_k: int | None = None, document_id: str | None = None) -> dict:
        top_k = top_k or self.settings.default_query_top_k
        bm25 = BM25Retriever(self.source_units)
        exact = ExactMatcher(self.source_units)
        dense = DenseRetriever()
        exact_results = exact.search(question, limit=self.settings.exact_match_limit)
        bm25_results = bm25.search(question, top_k=top_k * self.settings.bm25_top_k_multiplier)
        dense_results = dense.search(question, top_k=top_k, document_id=document_id)
        analysis = analyze_query(question)
        facts = self._graph_facts(question, document_id=document_id)
        fact_evidence = self._facts_to_evidence(facts)
        fused = reciprocal_rank_fusion(
            [exact_results, bm25_results, dense_results, fact_evidence],
            limit=self.settings.max_answer_contexts,
        )
        evidence = dedupe_evidence(exact_results + fused, limit=self.settings.max_answer_contexts) if analysis['asks_exact_lookup'] and exact_results else fused
        return {
            'method': 'graph',
            'question': question,
            'analysis': analysis,
            'evidence': evidence,
            'graph_facts': facts,
            'can_answer': bool(evidence),
            'insufficient_reason': None if evidence else 'No shared evidence was retrieved.',
        }

    def _graph_facts(self, question: str, document_id: str | None = None) -> list[dict]:
        terms = self._terms(question)
        store = Neo4jStore()
        try:
            return store.search_facts(terms, limit=self.settings.graph_fact_limit, document_id=document_id)
        except Exception:
            return self._graph_json_facts(terms, document_id=document_id)
        finally:
            store.close()

    def _graph_json_facts(self, terms: list[str], document_id: str | None = None) -> list[dict]:
        if not document_id:
            return []
        documents = DocumentStore()
        graph = documents.read_json(documents.graph_path(document_id), default={}) or {}
        facts = []
        lowered = [term.lower() for term in terms]
        for rel in graph.get('relationships', []) or []:
            haystack = ' '.join([
                str(rel.get('source', '')),
                str(rel.get('target', '')),
                str(rel.get('relation', '')),
                str(rel.get('evidence', '')),
            ]).lower()
            if lowered and not any(term in haystack for term in lowered):
                continue
            source_unit_ids = rel.get('source_unit_ids') or []
            facts.append({
                'document_id': rel.get('document_id'),
                'source': rel.get('source'),
                'relation': rel.get('relation'),
                'target': rel.get('target'),
                'evidence': rel.get('evidence'),
                'page': rel.get('page'),
                'section': rel.get('section'),
                'chunk_id': rel.get('source_chunk_id'),
                'source_unit_id': source_unit_ids[0] if source_unit_ids else rel.get('source_chunk_id'),
            })
            if len(facts) >= self.settings.graph_fact_limit:
                break
        return facts

    def _facts_to_evidence(self, facts: list[dict]) -> list[dict]:
        by_source: dict[str, dict] = {}
        for fact in facts:
            source_id = fact.get('source_unit_id') or fact.get('chunk_id')
            if not source_id:
                continue
            by_source[source_id] = {
                'source_id': source_id,
                'chunk_id': source_id,
                'document_id': fact.get('document_id'),
                'unit_type': 'graph_fact_evidence',
                'text': fact.get('evidence') or '',
                'page_start': fact.get('page'),
                'page_end': fact.get('page'),
                'section': fact.get('section'),
                'retrieval_channel': 'graph',
                'score': 1.0,
            }
        return [to_evidence_item(item, 'graph', score=item.get('score', 1.0)) for item in by_source.values()]

    def _terms(self, question: str) -> list[str]:
        analysis = analyze_query(question)
        terms = []
        terms.extend(str(n) for n in analysis['claim_numbers'])
        terms.extend(str(n) for n in analysis['example_numbers'])
        terms.extend(analysis['formulas'])
        terms.extend(self._capitalized_terms(question))
        for kw in self.settings.retrieval_keywords:
            if kw.lower() in question.lower():
                terms.append(kw)
        return list(dict.fromkeys(t for t in terms if t))[: self.settings.retrieval_term_limit]

    def _capitalized_terms(self, question: str) -> list[str]:
        import re

        return re.findall(r'\b[A-Z][A-Za-z0-9@\-()]{2,}\b', question)
