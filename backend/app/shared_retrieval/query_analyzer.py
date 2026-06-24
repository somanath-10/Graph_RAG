import re


def analyze_query(question: str) -> dict:
    q = question or ''
    lower = q.lower()
    claim_numbers = [int(n) for n in re.findall(r'\bclaim\s+(\d+)\b', lower)]
    example_numbers = [int(n) for n in re.findall(r'\bexample\s+(\d+)\b', lower)]
    formulas = re.findall(r'\b[A-Z][A-Za-z]?\d*(?:[@()/.-][A-Za-z0-9]+)+\b', q)
    numeric_values = re.findall(r'\b\d+(?:\.\d+)?\s*(?:%|wt%|mol%|mm|cm|nm|um|kg|g|mg|C|K|V|A|mA|h|min|s)\b', q)
    relationship_words = {
        'support', 'supports', 'supported', 'relate', 'relationship', 'improve',
        'reduces', 'causes', 'component', 'uses', 'produces', 'claim-to-example',
    }
    summary_words = {'summary', 'summarize', 'overview', 'explain', 'describe'}
    step_words = {'step', 'steps', 'method', 'process', 'procedure'}
    exact_words = {'exact', 'say', 'says', 'recite', 'recites', 'quote'}
    tokens = set(re.findall(r'[a-z0-9-]+', lower))
    return {
        'question': question,
        'claim_numbers': list(dict.fromkeys(claim_numbers)),
        'example_numbers': list(dict.fromkeys(example_numbers)),
        'formulas': list(dict.fromkeys(formulas)),
        'numeric_values': list(dict.fromkeys(numeric_values)),
        'asks_relationship': bool(tokens & relationship_words),
        'asks_summary': bool(tokens & summary_words),
        'asks_step_by_step': bool(tokens & step_words),
        'asks_exact_lookup': bool(tokens & exact_words or claim_numbers or example_numbers),
    }
