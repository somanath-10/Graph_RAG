import re
import hashlib
from pathlib import Path

from backend.app.config import get_settings


def detect_section(
    text: str,
    section_patterns: list[tuple[str, str]] | None = None,
    default_section: str | None = None,
) -> str:
    settings = get_settings()
    section_patterns = section_patterns or settings.section_pattern_list
    default_section = default_section or settings.body_section_name
    for section, pattern in section_patterns:
        if re.search(pattern, text):
            return section
    return default_section


def split_page_into_section_segments(
    text: str,
    current_section: str,
    section_patterns: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], str]:
    markers = []
    for order, (section, pattern) in enumerate(section_patterns):
        for match in re.finditer(pattern, text):
            markers.append((match.start(), match.end(), order, section))
    markers.sort(key=lambda item: (item[0], item[2]))

    non_overlapping = []
    last_end = -1
    for marker in markers:
        start, end, _, _ = marker
        if start < last_end:
            continue
        non_overlapping.append(marker)
        last_end = end

    if not non_overlapping:
        return [(current_section, text)], current_section

    segments = []
    first_start = non_overlapping[0][0]
    if first_start > 0:
        segments.append((current_section, text[:first_start]))

    for index, (start, _, _, section) in enumerate(non_overlapping):
        end = non_overlapping[index + 1][0] if index + 1 < len(non_overlapping) else len(text)
        segments.append((section, text[start:end]))
        current_section = section

    return segments, current_section


def chunk_pages(
    pages: list[dict],
    document_id: str,
    max_words: int | None = None,
    overlap: int | None = None,
    min_claim_words: int | None = None,
    claim_section: str | None = None,
    body_section: str | None = None,
    section_patterns: list[tuple[str, str]] | None = None,
    chunk_id_width: int | None = None,
) -> list[dict]:
    settings = get_settings()
    max_words = max_words or settings.chunk_max_words
    overlap = overlap if overlap is not None else settings.chunk_overlap_words
    min_chunk_words = settings.min_chunk_words
    min_claim_words = min_claim_words or settings.min_claim_words
    claim_section = claim_section or settings.claim_section_name
    body_section = body_section or settings.body_section_name
    chunk_id_width = chunk_id_width or settings.chunk_id_width

    chunks = []
    chunk_counter = 0
    current_section = body_section
    for page in pages:
        page_no = page['page']
        text = page.get('text', '')
        if not text.strip():
            continue
        segments, current_section = split_page_into_section_segments(text, current_section, section_patterns or settings.section_pattern_list)

        for section, segment_text in segments:
            segment_text = segment_text.strip()
            if not segment_text:
                continue

            # Split configured claim sections individually when possible.
            if section == claim_section:
                claim_parts = split_claims(segment_text)
                for claim in claim_parts:
                    if len(claim.split()) < min_claim_words:
                        continue
                    if not re.match(r'^\d+\.\s', claim) and chunks and chunks[-1]['section'] == claim_section:
                        chunks[-1]['text'] = f"{chunks[-1]['text']} {claim}".strip()
                        chunks[-1]['page_end'] = page_no
                        continue
                    chunks.append(_make_chunk(document_id, chunk_counter, claim, page_no, page_no, claim_section, chunk_id_width))
                    chunk_counter += 1
                continue

            words = segment_text.split()
            if len(words) < min_chunk_words:
                continue
            start = 0
            while start < len(words):
                end = min(start + max_words, len(words))
                chunk_text = ' '.join(words[start:end])
                chunks.append(_make_chunk(document_id, chunk_counter, chunk_text, page_no, page_no, section, chunk_id_width))
                chunk_counter += 1
                if end == len(words):
                    break
                start = max(0, end - overlap)
    return chunks


def split_claims(text: str) -> list[str]:
    # Matches claim boundaries like "1. A ..." through next numbered claim.
    parts = re.split(r'(?=\b\d+\.\s)', text)
    clean = []
    for p in parts:
        p = p.strip()
        if p:
            clean.append(p)
    return clean or [text]


def _make_chunk(
    document_id: str,
    index: int,
    text: str,
    page_start: int,
    page_end: int,
    section: str,
    chunk_id_width: int,
) -> dict:
    return {
        'chunk_id': f'{document_id}_chunk_{index:0{chunk_id_width}d}',
        'document_id': document_id,
        'text': text,
        'page_start': page_start,
        'page_end': page_end,
        'section': section,
    }


def document_id_from_path(path: str | Path) -> str:
    path = Path(path)
    if path.exists() and path.is_file():
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        return f'doc_{h.hexdigest()[:16]}'
    stem = path.stem
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', stem)
