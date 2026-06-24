from pathlib import Path
import fitz


def load_pdf_pages(pdf_path: str | Path) -> list[dict]:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f'PDF not found: {path}')

    doc = fitz.open(str(path))
    try:
        pages = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text('text') or ''
            pages.append({'page': i, 'text': text})
        return pages
    finally:
        doc.close()
