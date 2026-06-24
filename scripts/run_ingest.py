import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import get_settings
from backend.app.pipeline import PatentAccuracyRAGPipeline


def default_pdf_path() -> Path:
    settings = get_settings()
    raw_dir = Path(settings.raw_dir)
    if not raw_dir.is_absolute():
        raw_dir = ROOT / raw_dir
    configured = (settings.sample_pdf_filename or '').strip()
    if configured:
        return raw_dir / configured
    pdfs = sorted(raw_dir.glob('*.pdf'))
    if not pdfs:
        raise FileNotFoundError(f'No PDF files found in {raw_dir}')
    return pdfs[0]


if __name__ == '__main__':
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else default_pdf_path()
    result = PatentAccuracyRAGPipeline().ingest_pdf(str(pdf))
    print(result)
