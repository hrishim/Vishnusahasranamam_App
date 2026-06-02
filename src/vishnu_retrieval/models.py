from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PageRecord:
    page: int
    text: str
    avg_confidence: float | None
    low_confidence_ratio: float
    word_count: int
    warnings: list[str]
    source_pdf: str
    source_sha256: str
    source_docx: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    pages: list[int]
    page_start: int
    page_end: int
    avg_confidence: float | None
    warnings: list[str]
    token_count: int
    vector: dict[str, float]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
