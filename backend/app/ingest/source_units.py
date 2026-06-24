import re
from collections import defaultdict

from backend.app.config import get_settings
from backend.app.ingest.chunker import split_page_into_section_segments


def build_source_units(
    pages: list[dict],
    document_id: str,
    section_patterns: list[tuple[str, str]] | None = None,
) -> list[dict]:
    settings = get_settings()
    section_patterns = section_patterns or settings.section_pattern_list
    current_section = settings.body_section_name
    units: list[dict] = []
    section_counters: dict[str, int] = defaultdict(int)
    paragraph_counter = 0
    sentence_counter = 0

    for page in pages:
        page_no = int(page['page'])
        text = page.get('text', '') or ''
        if not text.strip():
            continue
        segments, current_section = split_page_into_section_segments(text, current_section, section_patterns)

        for section, segment_text in segments:
            segment_text = clean_text(segment_text)
            if not segment_text:
                continue

            section_counters[section] += 1
            section_id = f'{document_id}_p{page_no}_section_{slug(section)}_{section_counters[section]}'
            section_unit = make_source_unit(
                source_id=section_id,
                document_id=document_id,
                unit_type='section',
                text=segment_text,
                page_start=page_no,
                page_end=page_no,
                section=section,
            )
            units.append(section_unit)

            for paragraph in split_paragraphs(segment_text):
                paragraph = clean_text(paragraph)
                if word_count(paragraph) < settings.min_paragraph_words:
                    continue

                claim_number = detect_claim_number(paragraph) if section == settings.claim_section_name else None
                example_number = detect_example_number(paragraph, section)
                unit_type = 'claim' if claim_number is not None else 'example' if example_number is not None else 'paragraph'
                paragraph_counter += 1
                paragraph_id = build_structural_id(
                    document_id=document_id,
                    page_no=page_no,
                    unit_type=unit_type,
                    counter=paragraph_counter,
                    claim_number=claim_number,
                    example_number=example_number,
                )
                paragraph_unit = make_source_unit(
                    source_id=paragraph_id,
                    document_id=document_id,
                    unit_type=unit_type,
                    text=paragraph,
                    page_start=page_no,
                    page_end=page_no,
                    section=section,
                    claim_number=claim_number,
                    example_number=example_number,
                    parent_id=section_id,
                )
                units.append(paragraph_unit)
                section_unit['child_ids'].append(paragraph_id)

                for sentence in split_sentences(paragraph):
                    sentence = clean_text(sentence)
                    if len(sentence) < settings.sentence_split_min_chars:
                        continue
                    sentence_counter += 1
                    sentence_id = f'{paragraph_id}_sent_{sentence_counter}'
                    sentence_unit = make_source_unit(
                        source_id=sentence_id,
                        document_id=document_id,
                        unit_type='sentence',
                        text=sentence,
                        page_start=page_no,
                        page_end=page_no,
                        section=section,
                        claim_number=claim_number,
                        example_number=example_number,
                        parent_id=paragraph_id,
                    )
                    units.append(sentence_unit)
                    paragraph_unit['child_ids'].append(sentence_id)

    return units


def make_source_unit(
    source_id: str,
    document_id: str,
    unit_type: str,
    text: str,
    page_start: int,
    page_end: int,
    section: str,
    claim_number: int | None = None,
    example_number: int | None = None,
    parent_id: str | None = None,
) -> dict:
    return {
        'source_id': source_id,
        'chunk_id': source_id,
        'document_id': document_id,
        'unit_type': unit_type,
        'text': text,
        'page_start': page_start,
        'page_end': page_end,
        'section': section,
        'claim_number': claim_number,
        'example_number': example_number,
        'parent_id': parent_id,
        'child_ids': [],
        'token_count': word_count(text),
    }


def split_paragraphs(text: str) -> list[str]:
    rough = re.split(r'\n\s*\n+', text)
    paragraphs: list[str] = []
    for part in rough:
        part = part.strip()
        if not part:
            continue
        claim_parts = re.split(r'(?=\b\d+\.\s+[A-Z])', part)
        if len(claim_parts) > 1:
            paragraphs.extend(p.strip() for p in claim_parts if p.strip())
        else:
            paragraphs.append(part)
    return paragraphs


def split_sentences(text: str) -> list[str]:
    abbreviations = {'Fig.', 'FIG.', 'No.', 'Nos.', 'Inc.', 'Ltd.', 'Dr.', 'Mr.', 'Ms.', 'U.S.'}
    sentences = []
    start = 0
    for match in re.finditer(r'[.!?]\s+(?=[A-Z0-9\[])', text):
        end = match.end()
        candidate = text[start:end].strip()
        if any(candidate.endswith(abbrev) for abbrev in abbreviations):
            continue
        if candidate:
            sentences.append(candidate)
        start = end
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences or [text]


def detect_claim_number(text: str) -> int | None:
    match = re.match(r'\s*(\d+)\.\s+', text)
    return int(match.group(1)) if match else None


def detect_example_number(text: str, section: str | None = None) -> int | None:
    match = re.search(r'\bExample\s+(\d+)\b', f'{section or ""} {text}', re.IGNORECASE)
    return int(match.group(1)) if match else None


def clean_text(text: str) -> str:
    text = text.replace('\x00', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def word_count(text: str) -> int:
    return len(re.findall(r'\S+', text or ''))


def slug(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', value.strip().lower()).strip('_') or 'section'


def build_structural_id(
    document_id: str,
    page_no: int,
    unit_type: str,
    counter: int,
    claim_number: int | None = None,
    example_number: int | None = None,
) -> str:
    if claim_number is not None:
        return f'{document_id}_p{page_no}_claim_{claim_number}'
    if example_number is not None:
        return f'{document_id}_p{page_no}_example_{example_number}_{counter}'
    return f'{document_id}_p{page_no}_{unit_type}_{counter}'
