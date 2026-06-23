import re
from backend.app.embedding.embedder import Embedder
from backend.app.storage.qdrant_store import QdrantStore
from backend.app.storage.neo4j_store import Neo4jStore
from backend.app.llm.openai_client import OpenAIClient
from backend.app.config import get_settings
from backend.app.config_loader import load_text_file


class HybridRetriever:
    def __init__(self):
        self.settings = get_settings()
        self.embedder = Embedder()
        self.qdrant = QdrantStore()
        self.neo4j = Neo4jStore()
        self.openai = OpenAIClient()
        self.eval_system = load_text_file(self.settings.context_eval_system_prompt_path)
        self.eval_template = load_text_file(self.settings.context_eval_user_prompt_path)

    def detect_terms(self, question: str) -> list[str]:
        q = question.lower()
        terms = [t for t in self.settings.retrieval_seed_terms if t.lower() in q]
        # Add capitalized/formula-like tokens.
        terms.extend(re.findall(r'\b[A-Z][A-Za-z0-9@\-()]{2,}\b', question))
        # Add configured useful keywords.
        for kw in self.settings.retrieval_keywords:
            if kw.lower() in q and kw not in terms:
                terms.append(kw)
        return list(dict.fromkeys(terms))[: self.settings.retrieval_term_limit]

    def retrieve(self, question: str, top_k: int | None = None) -> dict:
        try:
            top_k = top_k or self.settings.default_query_top_k
            query_vector = self.embedder.embed_query(question)
            chunks = self.qdrant.search(query_vector, top_k=top_k)
            terms = self.detect_terms(question)
            facts = self.neo4j.search_facts(terms, limit=self.settings.graph_fact_limit)
            kept = self.evaluate_context(question, chunks)
            return {'chunks': chunks, 'graph_facts': facts, 'kept_contexts': kept, 'terms': terms}
        finally:
            self.neo4j.close()

    def evaluate_context(self, question: str, chunks: list[dict]) -> list[dict]:
        compact = []
        for c in chunks:
            compact.append({
                'chunk_id': c.get('chunk_id'),
                'page': c.get('page_start'),
                'section': c.get('section'),
                'text': (c.get('text') or '')[: self.settings.context_candidate_chars],
            })
        prompt = self.eval_template.format(question=question, contexts=compact)
        try:
            data = self.openai.json(prompt, self.eval_system, max_output_tokens=self.settings.context_eval_max_output_tokens)
            scored = {item.get('chunk_id'): item for item in data.get('contexts', []) if isinstance(item, dict)}
            out = []
            for c in chunks:
                score = scored.get(c.get('chunk_id'), {})
                keep = bool(score.get('keep', c.get('score', 0) > self.settings.context_relevance_threshold))
                relevance = int(score.get(
                    'relevance',
                    self.settings.context_default_keep_relevance if keep else self.settings.context_default_drop_relevance,
                ))
                item = dict(c)
                item['evaluation'] = {'keep': keep, 'relevance': relevance, 'reason': score.get('reason', '')}
                if keep:
                    out.append(item)
            if not out and self.settings.fallback_to_top_contexts_when_empty:
                fallback = []
                for c in chunks[: self.settings.min_answer_contexts]:
                    item = dict(c)
                    item['evaluation'] = {
                        'keep': True,
                        'relevance': self.settings.context_default_drop_relevance,
                        'reason': 'Fallback context retained because evaluator returned no kept contexts.',
                    }
                    fallback.append(item)
                return fallback
            return out[: self.settings.max_answer_contexts]
        except Exception as exc:
            print(f'Context evaluation failed, using top chunks: {exc}')
            return chunks[: self.settings.max_answer_contexts]
