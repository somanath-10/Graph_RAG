from backend.app.config import get_settings
from backend.app.shared_retrieval.bm25_retriever import BM25Retriever
from backend.app.shared_retrieval.dense_retriever import DenseRetriever
from backend.app.shared_retrieval.evidence import dedupe_evidence
from backend.app.shared_retrieval.evidence import to_evidence_item
from backend.app.shared_retrieval.exact_matcher import ExactMatcher
from backend.app.shared_retrieval.fusion import reciprocal_rank_fusion
from backend.app.shared_retrieval.query_analyzer import analyze_query
from backend.app.sprout_rag.beam_search import SproutBeamSearch
from backend.app.sprout_rag.hierarchy_store import SproutHierarchyStore


class SproutRAGRetriever:
    def __init__(self, source_units: list[dict], document_id: str):
        self.settings = get_settings()
        self.source_units = source_units
        self.source_by_id = {unit['source_id']: unit for unit in source_units}
        self.document_id = document_id

    def retrieve(self, question: str, top_k: int | None = None, document_id: str | None = None) -> dict:
        top_k = top_k or self.settings.default_query_top_k
        document_id = document_id or self.document_id
        bm25 = BM25Retriever(self.source_units)
        exact = ExactMatcher(self.source_units)
        dense = DenseRetriever()
        exact_results = exact.search(question, limit=self.settings.exact_match_limit)
        bm25_results = bm25.search(question, top_k=top_k * self.settings.bm25_top_k_multiplier)
        dense_results = dense.search(question, top_k=top_k, document_id=document_id)
        analysis = analyze_query(question)
        tree_results = self._tree_search(question, document_id)
        fused = reciprocal_rank_fusion(
            [exact_results, bm25_results, dense_results, tree_results],
            limit=self.settings.max_answer_contexts,
        )
        evidence = dedupe_evidence(exact_results + fused, limit=self.settings.max_answer_contexts) if analysis['asks_exact_lookup'] and exact_results else fused
        return {
            'method': 'sprout',
            'question': question,
            'analysis': analysis,
            'evidence': evidence,
            'tree_path': self._tree_path(tree_results),
            'graph_facts': [],
            'can_answer': bool(evidence),
            'insufficient_reason': None if evidence else 'No shared evidence was retrieved.',
        }

    def _tree_search(self, question: str, document_id: str) -> list[dict]:
        nodes = SproutHierarchyStore().load(document_id)
        if not nodes:
            return []
        candidates = SproutBeamSearch(nodes).search(
            question,
            beam_width=self.settings.sprout_beam_width,
            limit=self.settings.sprout_tree_candidate_limit,
        )
        evidence = []
        for node in candidates:
            source_ids = node.get('source_unit_ids') or []
            for source_id in source_ids:
                unit = self.source_by_id.get(source_id)
                if not unit or unit.get('unit_type') == 'section':
                    continue
                item = to_evidence_item(unit, 'sprout_tree', score=float(node.get('score', 0.0) or 0.0))
                item['tree_node_id'] = node.get('node_id')
                evidence.append(item)
        return evidence

    def _tree_path(self, evidence: list[dict]) -> list[dict]:
        return [
            {
                'tree_node_id': item.get('tree_node_id'),
                'source_id': item.get('source_id'),
                'section': item.get('section'),
                'score': item.get('score'),
            }
            for item in evidence[: self.settings.sprout_tree_candidate_limit]
        ]
