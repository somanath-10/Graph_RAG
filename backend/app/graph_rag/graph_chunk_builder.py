from backend.app.config import get_settings


def build_graph_evidence_chunks(source_units: list[dict]) -> list[dict]:
    settings = get_settings()
    preferred_types = {'claim', 'example', 'paragraph'}
    chunks = []
    for idx, unit in enumerate(source_units):
        if unit.get('unit_type') not in preferred_types:
            continue
        text = unit.get('text') or ''
        if not text.strip():
            continue
        chunks.append({
            'chunk_id': f"{unit['source_id']}_graph",
            'document_id': unit.get('document_id'),
            'source_unit_ids': [unit['source_id']],
            'text': text,
            'page_start': unit.get('page_start'),
            'page_end': unit.get('page_end'),
            'section': unit.get('section'),
            'claim_number': unit.get('claim_number'),
            'example_number': unit.get('example_number'),
            'unit_type': 'graph_evidence_chunk',
            'token_count': unit.get('token_count'),
        })
        if settings.max_graph_chunks and len(chunks) >= max(settings.max_graph_chunks * 4, settings.max_graph_chunks):
            break
    return chunks


def validate_graph_evidence(graph: dict, chunks: list[dict]) -> dict:
    by_id = {chunk.get('chunk_id'): chunk for chunk in chunks}
    relationships = []
    for rel in graph.get('relationships', []) or []:
        evidence = str(rel.get('evidence') or rel.get('evidence_quote') or '').strip()
        if not evidence:
            continue
        rel['evidence'] = evidence
        chunk = by_id.get(rel.get('source_chunk_id'))
        if chunk and evidence.lower() not in (chunk.get('text') or '').lower():
            continue
        relationships.append(rel)
    return {'entities': graph.get('entities', []) or [], 'relationships': relationships}
