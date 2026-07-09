from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .corrections import apply_curated_corrections
from .io import PAGES_DIR, PAGES_JSONL, ensure_dirs, read_pages, sha256_file, write_jsonl
from .models import PageRecord
from .textutil import normalize_text


XHTML_NS = "http://www.w3.org/1999/xhtml"
OPF_NS = "http://www.idpf.org/2007/opf"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"


@dataclass
class EpubParagraph:
    text: str
    href: str
    index: int


def rootfile_path(archive: ZipFile) -> str:
    root = ET.fromstring(archive.read("META-INF/container.xml"))
    rootfile = root.find(f".//{{{CONTAINER_NS}}}rootfile")
    if rootfile is None:
        raise ValueError("EPUB container does not declare a rootfile.")
    full_path = rootfile.attrib.get("full-path")
    if not full_path:
        raise ValueError("EPUB rootfile is missing full-path.")
    return full_path


def spine_xhtml_paths(archive: ZipFile, opf_path: str) -> list[str]:
    root = ET.fromstring(archive.read(opf_path))
    manifest: dict[str, str] = {}
    opf_dir = str(Path(opf_path).parent)
    if opf_dir == ".":
        opf_dir = ""
    for item in root.findall(f".//{{{OPF_NS}}}manifest/{{{OPF_NS}}}item"):
        item_id = item.attrib.get("id", "")
        href = item.attrib.get("href", "")
        media_type = item.attrib.get("media-type", "")
        if item_id and href and media_type == "application/xhtml+xml":
            manifest[item_id] = str(Path(opf_dir) / href) if opf_dir else href

    paths: list[str] = []
    for itemref in root.findall(f".//{{{OPF_NS}}}spine/{{{OPF_NS}}}itemref"):
        if itemref.attrib.get("linear") == "no":
            continue
        href = manifest.get(itemref.attrib.get("idref", ""))
        if href:
            paths.append(href)
    return paths


def element_text(element: ET.Element) -> str:
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in list(node):
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    text = html.unescape("".join(parts)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return normalize_text(text).strip()


def read_epub_paragraphs(epub_path: Path) -> list[EpubParagraph]:
    paragraphs: list[EpubParagraph] = []
    with ZipFile(epub_path) as archive:
        opf_path = rootfile_path(archive)
        for href in spine_xhtml_paths(archive, opf_path):
            if href not in archive.namelist():
                continue
            root = ET.fromstring(archive.read(href))
            body = root.find(f".//{{{XHTML_NS}}}body")
            if body is None:
                continue
            for node in body.iter():
                tag = node.tag.rsplit("}", 1)[-1]
                if tag not in {"h1", "h2", "h3", "p", "li"}:
                    continue
                text = element_text(node)
                if text:
                    paragraphs.append(EpubParagraph(text=text, href=href, index=len(paragraphs)))
    return paragraphs


def compact(text: str) -> str:
    return re.sub(r"\s+", "", normalize_text(text)).casefold()


def align_paragraphs_to_pages(paragraphs: list[EpubParagraph], alignment_pages_jsonl: Path) -> list[int]:
    if not alignment_pages_jsonl.exists():
        return list(range(1, len(paragraphs) + 1))

    existing_pages = read_pages(alignment_pages_jsonl)
    compact_pages = [(page.page, compact(page.text)) for page in existing_pages]
    assignments: list[int] = []
    last_page = existing_pages[0].page if existing_pages else 1
    search_start = 0

    for paragraph in paragraphs:
        text = compact(paragraph.text)
        anchors = [text[:120], text[:80], text[:50]]
        anchors = [anchor for anchor in anchors if len(anchor) >= 35]
        found: tuple[int, int] | None = None
        for anchor in anchors:
            for offset in range(search_start, len(compact_pages)):
                page_num, page_text = compact_pages[offset]
                if anchor in page_text:
                    found = (offset, page_num)
                    break
            if found:
                break
        if found:
            search_start, last_page = found
        assignments.append(last_page)
    return assignments


def run_epub_ingest(
    epub_path: Path,
    out_jsonl: Path = PAGES_JSONL,
    pdf_path: Path | None = None,
    alignment_pages_jsonl: Path = PAGES_JSONL,
) -> list[PageRecord]:
    ensure_dirs()
    epub_path = epub_path.resolve()
    if not epub_path.exists():
        raise FileNotFoundError(epub_path)

    source_epub_hash = sha256_file(epub_path)
    source_pdf = str(pdf_path.resolve()) if pdf_path else str(epub_path)
    paragraphs = read_epub_paragraphs(epub_path)
    assignments = align_paragraphs_to_pages(paragraphs, alignment_pages_jsonl)

    grouped: dict[int, list[str]] = {}
    for stale_page in PAGES_DIR.glob("page_*.txt"):
        stale_page.unlink()
    for paragraph, page_num in zip(paragraphs, assignments, strict=False):
        grouped.setdefault(page_num, []).append(paragraph.text)

    records: list[PageRecord] = []
    for page_num in sorted(grouped):
        text = apply_curated_corrections(normalize_text("\n\n".join(grouped[page_num]).strip()))
        records.append(
            PageRecord(
                page=page_num,
                text=text,
                avg_confidence=None,
                low_confidence_ratio=0.0,
                word_count=len(text.split()),
                warnings=[],
                source_pdf=source_pdf,
                source_sha256=source_epub_hash,
                source_epub=str(epub_path),
            )
        )
        (PAGES_DIR / f"page_{page_num:04d}.txt").write_text(text + "\n", encoding="utf-8")

    write_jsonl(out_jsonl, [record.to_json() for record in records])
    return records
