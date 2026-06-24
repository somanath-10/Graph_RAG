from typing import Iterable


def to_evidence_item(item: dict, retrieval_channel: str, score: float = 0.0) -> dict:
    source_id = item.get('source_id') or item.get('chunk_id')
    return {
        'source_id': source_id,
        'chunk_id': source_id,
        'document_id': item.get('document_id'),
        'unit_type': item.get('unit_type') or item.get('type'),
        'text': item.get('text') or '',
        'page_start': item.get('page_start') or item.get('page'),
        'page_end': item.get('page_end') or item.get('page_start') or item.get('page'),
        'section': item.get('section'),
        'claim_number': item.get('claim_number'),
        'example_number': item.get('example_number'),
        'retrieval_channel': retrieval_channel,
        'score': float(item.get('score', score) or score),
    }


def dedupe_evidence(items: Iterable[dict], limit: int | None = None) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        source_id = item.get('source_id') or item.get('chunk_id')
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        out.append(item)
        if limit is not None and len(out) >= limit:
            break
    return out
