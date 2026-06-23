import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return project_root() / candidate


@lru_cache
def load_json_file(path: str) -> Any:
    resolved = resolve_path(path)
    return json.loads(resolved.read_text(encoding='utf-8'))


@lru_cache
def load_text_file(path: str) -> str:
    resolved = resolve_path(path)
    return resolved.read_text(encoding='utf-8').strip()
