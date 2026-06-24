from backend.app.config import get_settings
from backend.app.shared_retrieval.evidence import to_evidence_item
from backend.app.shared_retrieval.query_analyzer import analyze_query


class ExactMatcher:
    def __init__(self, source_units: list[dict]):
        self.settings = get_settings()
        self.source_units = source_units

    def search(self, question: str, limit: int | None = None) -> list[dict]:
        limit = limit or self.settings.exact_match_limit
        analysis = analyze_query(question)
        matches: list[dict] = []
        for unit in self.source_units:
            score = self._score_unit(unit, analysis)
            if score <= 0:
                continue
            item = to_evidence_item(unit, 'exact', score=score)
            item['score'] = score
            matches.append(item)
        matches.sort(key=lambda item: item['score'], reverse=True)
        return matches[:limit]

    def _score_unit(self, unit: dict, analysis: dict) -> float:
        score = 0.0
        if unit.get('claim_number') in analysis['claim_numbers']:
            score += 6.0 if unit.get('unit_type') == 'claim' else 3.0
        if unit.get('example_number') in analysis['example_numbers']:
            score += 6.0 if unit.get('unit_type') == 'example' else 3.0

        text = (unit.get('text') or '').lower()
        for formula in analysis['formulas']:
            if formula.lower() in text:
                score += 2.5
        for value in analysis['numeric_values']:
            if value.lower() in text:
                score += 2.0
        return score
