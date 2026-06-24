import re

from backend.app.config import get_settings


def normalize_patent_text(text: str, replacements: dict[str, str] | None = None) -> str:
    if replacements is None:
        replacements = get_settings().normalizer_replacements

    encoded_minus = '\u00e2\u02c6\u2019'
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Convert generic patent formula markup, e.g. X.sub.2 -> X2 and unit exponents.
    text = re.sub(r'\.sub\.([A-Za-z0-9]+)', r'\1', text)
    text = re.sub(r'\.sup\.([+\-\u2212]?\d+)', r'\1', text)
    text = re.sub(r'\.sup\.' + re.escape(encoded_minus) + r'?(\d+)', r'-\1', text)
    text = text.replace(encoded_minus, '-')
    text = text.replace('\u2212', '-')
    text = re.sub(r'\b([A-Za-z]+[0-9]*)\s+g-1\b', r'\1/g', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t\f\v]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def normalize_pages(pages: list[dict], replacements: dict[str, str] | None = None) -> list[dict]:
    return [{'page': p['page'], 'text': normalize_patent_text(p.get('text', ''), replacements)} for p in pages]
