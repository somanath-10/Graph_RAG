from backend.app.shared_retrieval.evidence import dedupe_evidence


def reciprocal_rank_fusion(result_sets: list[list[dict]], limit: int | None = None, k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    channels: dict[str, set[str]] = {}
    for results in result_sets:
        for rank, item in enumerate(results, start=1):
            source_id = item.get('source_id') or item.get('chunk_id')
            if not source_id:
                continue
            scores[source_id] = scores.get(source_id, 0.0) + 1.0 / (k + rank)
            items[source_id] = item
            channels.setdefault(source_id, set()).add(item.get('retrieval_channel') or 'unknown')

    fused = []
    for source_id, item in items.items():
        merged = dict(item)
        merged['score'] = scores[source_id]
        merged['retrieval_channel'] = '+'.join(sorted(channels.get(source_id, {'unknown'})))
        fused.append(merged)
    fused.sort(key=lambda item: item['score'], reverse=True)
    return dedupe_evidence(fused, limit=limit)
