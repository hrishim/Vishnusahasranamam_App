from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .corrections import apply_curated_corrections
from .io import PAGES_DIR, PAGES_JSONL, ensure_dirs, read_pages, sha256_file, write_jsonl
from .models import PageRecord
from .textutil import normalize_text


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"

PAGE_HEADER_RE = re.compile(
    r"^\s*(?:(?P<left>\d{1,4})\s+)?(?:VISNUSAHASRANAMA|VIṢṆUSUHASRAṆĀMĀ)(?:\s+(?P<right>\d{1,4}))?\s*$",
    re.IGNORECASE,
)
NUMBER_ONLY_RE = re.compile(r"^\s*\d{1,4}\s*$")
INFERRED_ALIGNMENT_WARNING_RE = re.compile(
    r"DOCX book page (?P<book>\d{1,4}) was not directly aligned to a PDF page; citation page is inferred\."
)


@dataclass
class BookPage:
    book_page: int | None
    paragraphs: list[str]


def paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []

    def walk(element: ET.Element) -> None:
        tag = element.tag
        if tag == f"{W}t":
            parts.append(element.text or "")
        elif tag == f"{W}tab":
            parts.append("\t")
        elif tag == f"{W}br":
            parts.append("\n")
        for child in list(element):
            walk(child)

    walk(paragraph)
    return normalize_text("".join(parts)).strip()


def read_docx_paragraphs(docx_path: Path) -> list[str]:
    with ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ET.fromstring(document_xml)
    body = root.find(f"{W}body")
    if body is None:
        return []
    paragraphs: list[str] = []
    for paragraph in body.findall(f"{W}p"):
        text = paragraph_text(paragraph)
        if text:
            paragraphs.append(text)
    return paragraphs


def page_header_number(text: str) -> int | None:
    match = PAGE_HEADER_RE.match(text)
    if not match:
        return None
    value = match.group("left") or match.group("right")
    return int(value) if value else None


def segment_book_pages(paragraphs: list[str]) -> list[BookPage]:
    pages: list[BookPage] = []
    current_page: int | None = None
    current_paragraphs: list[str] = []

    for paragraph in paragraphs:
        marker = page_header_number(paragraph)
        if marker is not None:
            if current_paragraphs:
                pages.append(BookPage(current_page, current_paragraphs))
            current_page = marker
            current_paragraphs = []
            continue
        if NUMBER_ONLY_RE.match(paragraph):
            continue
        current_paragraphs.append(paragraph)

    if current_paragraphs:
        pages.append(BookPage(current_page, current_paragraphs))
    return pages


def book_page_markers(text: str) -> list[int]:
    markers: list[int] = []
    for line in text.splitlines():
        marker = page_header_number(line)
        if marker is not None:
            markers.append(marker)
    return markers


def align_book_pages_to_pdf(pdf_pages_jsonl: Path) -> dict[int, int]:
    mapping: dict[int, int] = {}
    if not pdf_pages_jsonl.exists():
        return mapping
    for page in read_pages(pdf_pages_jsonl):
        for marker in book_page_markers(page.text):
            mapping.setdefault(marker, page.page)
        for warning in page.warnings:
            match = INFERRED_ALIGNMENT_WARNING_RE.search(warning)
            if match:
                mapping.setdefault(int(match.group("book")), page.page)
    return mapping


def align_book_pages_by_text(book_pages: list[BookPage], pages_jsonl: Path) -> dict[int, int]:
    mapping: dict[int, int] = {}
    if not pages_jsonl.exists():
        return mapping
    existing_pages = read_pages(pages_jsonl)
    compact_pages = [
        (existing_page.page, re.sub(r"\s+", "", normalize_text(existing_page.text)))
        for existing_page in existing_pages
    ]
    page_index = 0
    for book_page in book_pages:
        if book_page.book_page is None:
            continue
        anchors = [
            re.sub(r"\s+", "", normalize_text(paragraph))[:80]
            for paragraph in book_page.paragraphs
            if len(re.sub(r"\s+", "", normalize_text(paragraph))) > 40
        ]
        found_index = None
        for anchor in anchors[:5]:
            for index in range(page_index, len(compact_pages)):
                page_num, existing_text = compact_pages[index]
                if anchor in existing_text:
                    mapping.setdefault(book_page.book_page, page_num)
                    found_index = index
                    break
            if book_page.book_page in mapping:
                break
        if found_index is not None:
            page_index = found_index
    return mapping


def logical_page_for_book_page(book_page: int | None, alignment: dict[int, int], fallback: int) -> int:
    if book_page is None:
        return fallback
    if book_page in alignment:
        return alignment[book_page]

    lower = [(book, pdf) for book, pdf in alignment.items() if book < book_page]
    upper = [(book, pdf) for book, pdf in alignment.items() if book > book_page]
    if lower and upper:
        lower_book, lower_pdf = max(lower)
        upper_book, upper_pdf = min(upper)
        if upper_book != lower_book:
            ratio = (book_page - lower_book) / (upper_book - lower_book)
            return max(1, round(lower_pdf + ratio * (upper_pdf - lower_pdf)))
    if lower:
        lower_book, lower_pdf = max(lower)
        return max(1, lower_pdf + max(0, book_page - lower_book))
    if upper:
        upper_book, upper_pdf = min(upper)
        return max(1, upper_pdf - max(0, upper_book - book_page))
    return fallback


def run_docx_ingest(
    docx_path: Path,
    out_jsonl: Path = PAGES_JSONL,
    pdf_path: Path | None = None,
    alignment_pages_jsonl: Path = PAGES_JSONL,
) -> list[PageRecord]:
    ensure_dirs()
    docx_path = docx_path.resolve()
    if not docx_path.exists():
        raise FileNotFoundError(docx_path)

    source_docx_hash = sha256_file(docx_path)
    source_pdf = str(pdf_path.resolve()) if pdf_path else str(docx_path)
    book_pages = segment_book_pages(read_docx_paragraphs(docx_path))
    alignment = align_book_pages_to_pdf(alignment_pages_jsonl)
    if len(alignment) < max(20, len(book_pages) // 4):
        alignment.update(align_book_pages_by_text(book_pages, alignment_pages_jsonl))

    grouped: dict[int, dict[str, list[str]]] = {}
    for stale_page in PAGES_DIR.glob("page_*.txt"):
        stale_page.unlink()
    for fallback_page, book_page in enumerate(book_pages, start=1):
        page_num = logical_page_for_book_page(book_page.book_page, alignment, fallback_page)
        bucket = grouped.setdefault(page_num, {"paragraphs": [], "warnings": []})
        bucket["paragraphs"].extend(book_page.paragraphs)
        if book_page.book_page is not None and book_page.book_page not in alignment:
            bucket["warnings"].append(
                f"DOCX book page {book_page.book_page} was not directly aligned to a PDF page; citation page is inferred."
            )

    records: list[PageRecord] = []
    for page_num in sorted(grouped):
        text = apply_curated_corrections(normalize_text("\n\n".join(grouped[page_num]["paragraphs"]).strip()))
        warnings = grouped[page_num]["warnings"]
        records.append(
            PageRecord(
                page=page_num,
                text=text,
                avg_confidence=None,
                low_confidence_ratio=0.0,
                word_count=len(text.split()),
                warnings=warnings,
                source_pdf=source_pdf,
                source_sha256=source_docx_hash,
                source_docx=str(docx_path),
            )
        )
        (PAGES_DIR / f"page_{page_num:04d}.txt").write_text(text + "\n", encoding="utf-8")

    write_jsonl(out_jsonl, [record.to_json() for record in records])
    return records
