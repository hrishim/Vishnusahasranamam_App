from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from .corrections import apply_curated_corrections
from .io import PAGES_DIR, ensure_dirs, sha256_file, write_jsonl
from .models import PageRecord
from .textutil import normalize_text


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required tool not found: {name}")
    return path


def pdf_page_count(pdf_path: Path) -> int:
    require_tool("pdfinfo")
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError("Could not determine PDF page count.")


def extract_embedded_pages(pdf_path: Path, from_page: int, to_page: int) -> dict[int, str]:
    if not shutil.which("pdftotext"):
        return {}
    result = subprocess.run(
        [
            "pdftotext",
            "-layout",
            "-enc",
            "UTF-8",
            "-f",
            str(from_page),
            "-l",
            str(to_page),
            str(pdf_path),
            "-",
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return {}
    parts = result.stdout.split("\f")
    pages: dict[int, str] = {}
    for offset, part in enumerate(parts[: to_page - from_page + 1]):
        pages[from_page + offset] = normalize_text(part.strip())
    return pages


def render_page(pdf_path: Path, page: int, out_dir: Path, dpi: int) -> Path:
    require_tool("pdftoppm")
    prefix = out_dir / f"page_{page:04d}"
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page),
            "-l",
            str(page),
            "-r",
            str(dpi),
            "-png",
            str(pdf_path),
            str(prefix),
        ],
        check=True,
        capture_output=True,
    )
    rendered = sorted(out_dir.glob(f"page_{page:04d}-*.png"))
    if not rendered:
        raise RuntimeError(f"PDF page {page} did not render.")
    return rendered[0]


def tesseract_tsv(image_path: Path, langs: str, psm: int) -> str:
    require_tool("tesseract")
    result = subprocess.run(
        [
            "tesseract",
            str(image_path),
            "stdout",
            "-l",
            langs,
            "--psm",
            str(psm),
            "--oem",
            "1",
            "tsv",
            "-c",
            "preserve_interword_spaces=1",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def page_text_from_tsv(tsv_text: str) -> tuple[str, float | None, float, int]:
    rows = csv.DictReader(tsv_text.splitlines(), delimiter="\t")
    lines: dict[tuple[int, int, int], list[tuple[int, str, float | None]]] = defaultdict(list)
    confidences: list[float] = []
    low_conf = 0
    words = 0

    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(row.get("conf") or "-1")
        except ValueError:
            conf = -1.0
        conf_value = conf if conf >= 0 else None
        if conf_value is not None:
            confidences.append(conf_value)
            if conf_value < 55:
                low_conf += 1
        words += 1
        key = (
            int(row.get("block_num") or 0),
            int(row.get("par_num") or 0),
            int(row.get("line_num") or 0),
        )
        x = int(float(row.get("left") or 0))
        lines[key].append((x, text, conf_value))

    paragraphs: list[str] = []
    current_block_par: tuple[int, int] | None = None
    current_lines: list[str] = []

    for block, par, line in sorted(lines):
        block_par = (block, par)
        if current_block_par is not None and block_par != current_block_par:
            if current_lines:
                paragraphs.append("\n".join(current_lines))
            current_lines = []
        current_block_par = block_par
        words_on_line = [word for _, word, _ in sorted(lines[(block, par, line)])]
        current_lines.append(" ".join(words_on_line))

    if current_lines:
        paragraphs.append("\n".join(current_lines))

    avg_conf = sum(confidences) / len(confidences) if confidences else None
    low_ratio = low_conf / len(confidences) if confidences else 1.0
    return normalize_text("\n\n".join(paragraphs).strip()), avg_conf, low_ratio, words


def warnings_for_page(text: str, avg_conf: float | None, low_ratio: float, word_count: int) -> list[str]:
    warnings: list[str] = []
    if avg_conf is None:
        warnings.append("No OCR confidence values were available for this page.")
    elif avg_conf < 70:
        warnings.append(f"Low average OCR confidence: {avg_conf:.1f}.")
    if low_ratio > 0.25:
        warnings.append(f"Many low-confidence OCR words: {low_ratio:.0%}.")
    if word_count < 15 or len(text) < 80:
        warnings.append("Sparse extracted text; this page may be blank, illustrated, or poorly recognized.")
    return warnings


def run_ocr(
    pdf_path: Path,
    out_jsonl: Path,
    from_page: int | None = None,
    to_page: int | None = None,
    dpi: int = 350,
    langs: str = "san+eng",
    psm: int = 6,
    mode: str = "auto",
) -> list[PageRecord]:
    ensure_dirs()
    pdf_path = pdf_path.resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    page_count = pdf_page_count(pdf_path)
    start = from_page or 1
    end = to_page or page_count
    if start < 1 or end > page_count or start > end:
        raise ValueError(f"Invalid page range {start}-{end} for {page_count} pages.")

    source_hash = sha256_file(pdf_path)
    embedded_pages: dict[int, str] = {}
    if mode in {"auto", "embedded"}:
        embedded_pages = extract_embedded_pages(pdf_path, start, end)

    records: list[PageRecord] = []
    with tempfile.TemporaryDirectory(prefix="vishnu_ocr_") as tmp:
        tmp_dir = Path(tmp)
        for page in range(start, end + 1):
            embedded_text = embedded_pages.get(page, "")
            embedded_word_count = len(embedded_text.split())
            if mode in {"auto", "embedded"} and embedded_word_count >= 15:
                text = embedded_text
                avg_conf = None
                low_ratio = 0.0
                word_count = embedded_word_count
                warnings = []
            elif mode == "embedded":
                text = embedded_text
                avg_conf = None
                low_ratio = 1.0
                word_count = embedded_word_count
                warnings = warnings_for_page(text, avg_conf, low_ratio, word_count)
            else:
                image_path = render_page(pdf_path, page, tmp_dir, dpi)
                text, avg_conf, low_ratio, word_count = page_text_from_tsv(tesseract_tsv(image_path, langs, psm))
                warnings = warnings_for_page(text, avg_conf, low_ratio, word_count)
            text = apply_curated_corrections(text)
            word_count = len(text.split())
            record = PageRecord(
                page=page,
                text=text,
                avg_confidence=avg_conf,
                low_confidence_ratio=low_ratio,
                word_count=word_count,
                warnings=warnings,
                source_pdf=str(pdf_path),
                source_sha256=source_hash,
            )
            records.append(record)
            (PAGES_DIR / f"page_{page:04d}.txt").write_text(text + "\n", encoding="utf-8")

    write_jsonl(out_jsonl, [record.to_json() for record in records])
    return records
