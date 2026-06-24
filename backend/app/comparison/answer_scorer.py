def score_answer(result: dict) -> dict:
    validation = result.get('citation_validation') or {}
    evidence = result.get('sources') or []
    citation_precision = float(validation.get('citation_precision', 0.0) or 0.0)
    unsupported = int(validation.get('unsupported_claim_count', 0) or 0)
    channels = {item.get('retrieval_channel') for item in evidence if item.get('retrieval_channel')}
    evidence_score = min(len(evidence), 8) / 8
    channel_score = min(len(channels), 4) / 4
    latency_ms = float(result.get('latency_ms', 0.0) or 0.0)
    score = 0.0
    score += citation_precision * 35
    score += evidence_score * 30
    score += channel_score * 20
    score += (0 if result.get('insufficient_evidence') else 10)
    score -= unsupported * 10
    score -= min(latency_ms / 1000, 10) * 0.5
    return {
        'score': round(max(score, 0.0), 2),
        'citation_precision': citation_precision,
        'evidence_count': len(evidence),
        'retrieval_channels': sorted(channels),
        'unsupported_claim_count': unsupported,
        'latency_ms': round(latency_ms, 2),
    }


def choose_winner(graph_result: dict, sprout_result: dict) -> dict:
    graph_score = score_answer(graph_result)
    sprout_score = score_answer(sprout_result)
    if graph_score['score'] > sprout_score['score']:
        winner = 'graph_rag'
        if has_channel(graph_score, 'graph'):
            reason = 'GraphRAG retrieved stronger cited evidence with graph-linked support.'
        else:
            reason = 'GraphRAG retrieved stronger cited evidence from the shared retrieval channels.'
    elif sprout_score['score'] > graph_score['score']:
        winner = 'sprout_rag'
        if has_channel(sprout_score, 'sprout_tree'):
            reason = 'SproutRAG retrieved stronger cited evidence through the document hierarchy.'
        else:
            reason = 'SproutRAG retrieved stronger cited evidence from the shared retrieval channels.'
    else:
        winner = 'tie'
        reason = 'Both methods produced comparable cited evidence.'
    return {
        'winner': winner,
        'reason': reason,
        'graph_score': graph_score,
        'sprout_score': sprout_score,
    }


def has_channel(score: dict, channel: str) -> bool:
    return any(channel in item for item in score.get('retrieval_channels', []))
