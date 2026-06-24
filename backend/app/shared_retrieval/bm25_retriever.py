import math
import re
from collections import Counter, defaultdict

from backend.app.config import get_settings
from backend.app.shared_retrieval.evidence import to_evidence_item


TOKEN_RE = re.compile(r'[A-Za-z0-9@%./+-]+')


class BM25Retriever:
    def __init__(self, source_units: list[dict]):
        self.settings = get_settings()
        self.source_units = [u for u in source_units if (u.get('text') or '').strip()]
        self.doc_tokens = [tokenize(u.get('text') or '') for u in self.source_units]
        self.doc_freqs = self._doc_freqs()
        self.avgdl = sum(len(tokens) for tokens in self.doc_tokens) / max(len(self.doc_tokens), 1)

    def search(self, question: str, top_k: int | None = None) -> list[dict]:
        top_k = top_k or self.settings.default_query_top_k
        query_terms = tokenize(question)
        if not query_terms:
            return []

        scored = []
        query_counts = Counter(query_terms)
        for idx, tokens in enumerate(self.doc_tokens):
            score = self._score(tokens, query_counts)
            if score <= 0:
                continue
            item = to_evidence_item(self.source_units[idx], 'bm25', score=score)
            scored.append(item)
        scored.sort(key=lambda item: item['score'], reverse=True)
        return scored[:top_k]

    def _doc_freqs(self) -> dict[str, int]:
        freqs: dict[str, int] = defaultdict(int)
        for tokens in self.doc_tokens:
            for term in set(tokens):
                freqs[term] += 1
        return dict(freqs)

    def _score(self, tokens: list[str], query_counts: Counter) -> float:
        k1 = 1.5
        b = 0.75
        counts = Counter(tokens)
        doc_len = max(len(tokens), 1)
        score = 0.0
        total_docs = max(len(self.doc_tokens), 1)
        for term, qf in query_counts.items():
            tf = counts.get(term, 0)
            if not tf:
                continue
            df = self.doc_freqs.get(term, 0)
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * doc_len / max(self.avgdl, 1))
            score += idf * (tf * (k1 + 1) / denom) * qf
        return score


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or '')]
