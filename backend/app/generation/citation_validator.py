import re


SOURCE_CITATION_RE = re.compile(r'\[([A-Za-z0-9_.:-]+)\]')


class CitationValidator:
    def validate(self, answer: str, evidence: list[dict]) -> dict:
        valid_ids = {item.get('source_id') for item in evidence if item.get('source_id')}
        cited_ids = [match.group(1) for match in SOURCE_CITATION_RE.finditer(answer or '')]
        invalid_ids = [source_id for source_id in cited_ids if source_id not in valid_ids]
        factual_sentences = [
            s.strip()
            for s in re.split(r'(?<=[.!?])\s+', answer or '')
            if s.strip() and 'insufficient' not in s.lower()
        ]
        unsupported = [
            sentence for sentence in factual_sentences
            if not any(f'[{source_id}]' in sentence for source_id in valid_ids)
        ]
        has_citations = bool(cited_ids)
        citation_precision = 0.0
        if cited_ids:
            citation_precision = (len(cited_ids) - len(invalid_ids)) / len(cited_ids)
        return {
            'valid': has_citations and not invalid_ids and not unsupported,
            'cited_source_ids': cited_ids,
            'invalid_source_ids': invalid_ids,
            'unsupported_claims': unsupported,
            'unsupported_claim_count': len(unsupported),
            'citation_precision': citation_precision,
        }
