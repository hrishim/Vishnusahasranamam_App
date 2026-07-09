from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

from .models import PageRecord


def project_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = project_root()
DATA_DIR = PROJECT_ROOT / "data"
OCR_DIR = DATA_DIR / "ocr"
PAGES_DIR = OCR_DIR / "pages"
INDEX_DIR = DATA_DIR / "index"
PAGES_JSONL = OCR_DIR / "pages.jsonl"
INDEX_JSON = INDEX_DIR / "index.json"
SLOKAS_JSON = INDEX_DIR / "slokas.json"
NAMA_NUMBERS_JSON = INDEX_DIR / "nama_numbers.json"
DERIVATION_OVERRIDES_JSON = INDEX_DIR / "derivation_overrides.json"


def ensure_dirs() -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_pages(path: Path = PAGES_JSONL) -> list[PageRecord]:
    pages: list[PageRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                pages.append(PageRecord(**json.loads(line)))
    return pages


def write_index(index: dict, path: Path = INDEX_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def read_index(path: Path = INDEX_JSON) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
