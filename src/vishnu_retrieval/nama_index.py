from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .io import NAMA_NUMBERS_JSON
from .textutil import normalize_text


DEVANAGARI_DIGIT_TRANS = str.maketrans("०१२३४५६७८९", "0123456789")
DEVANAGARI_NAME_RE = r"[\u0900-\u097F][\u0900-\u097F\s\u200c\u200dऽ:;\-()]+?"
INDEX_ENTRY_RE = re.compile(
    rf"(?P<name>{DEVANAGARI_NAME_RE})\s+"
    r"(?P<numbers>[०-९0-9][०-९0-9,\.\s]{0,20})"
    r"(?=\s{2,}|\n|$)"
)


@dataclass
class NamaNumberRow:
    name: str
    numbers: list[int]
    raw: str


@dataclass
class RejectedNamaNumberRow:
    name: str
    raw_numbers: str
    raw: str
    reason: str


def devanagari_key(text: str) -> str:
    text = normalize_text(text).replace(":", "ः")
    return re.sub(r"[^\u0900-\u097F]", "", text)


def extract_pdf_text(pdf_path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise RuntimeError("pdftotext is required to read the index PDF.")
    result = subprocess.run(
        [pdftotext, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def parse_number_list(raw_numbers: str) -> tuple[list[int], list[str]]:
    normalized = raw_numbers.translate(DEVANAGARI_DIGIT_TRANS).replace(".", ",")
    numbers: list[int] = []
    rejected: list[str] = []
    for value_text in re.findall(r"\d+", normalized):
        value = int(value_text)
        if 1 <= value <= 1000:
            numbers.append(value)
        else:
            rejected.append(value_text)
    return sorted(set(numbers)), rejected


def parse_index_text(text: str) -> tuple[list[NamaNumberRow], list[RejectedNamaNumberRow]]:
    rows_by_key: dict[str, NamaNumberRow] = {}
    rejected_rows: list[RejectedNamaNumberRow] = []

    for match in INDEX_ENTRY_RE.finditer(normalize_text(text)):
        raw = match.group(0).replace("\n", " ").strip()
        name = " ".join(match.group("name").split())
        raw_numbers = match.group("numbers").strip()
        numbers, rejected_numbers = parse_number_list(raw_numbers)
        if rejected_numbers:
            rejected_rows.append(
                RejectedNamaNumberRow(
                    name=name,
                    raw_numbers=raw_numbers,
                    raw=raw,
                    reason="Number outside 1-1000; likely OCR error.",
                )
            )
        if not numbers:
            continue
        key = devanagari_key(name)
        if not key:
            continue
        if key not in rows_by_key:
            rows_by_key[key] = NamaNumberRow(name=name, numbers=numbers, raw=raw)
        else:
            existing = rows_by_key[key]
            existing.numbers = sorted(set(existing.numbers).union(numbers))
            existing.raw = f"{existing.raw} | {raw}"

    return sorted(rows_by_key.values(), key=lambda row: (row.name, row.numbers)), rejected_rows


def build_nama_number_index(source_pdf: Path, out_path: Path = NAMA_NUMBERS_JSON) -> dict:
    text = extract_pdf_text(source_pdf)
    rows, rejected = parse_index_text(text)
    covered_numbers = sorted({number for row in rows for number in row.numbers})
    payload = {
        "schema_version": 1,
        "source_pdf": str(source_pdf.resolve()),
        "parsed_name_count": len(rows),
        "covered_number_count": len(covered_numbers),
        "covered_numbers": covered_numbers,
        "rows": [
            {
                "name": row.name,
                "key": devanagari_key(row.name),
                "numbers": row.numbers,
                "raw": row.raw,
            }
            for row in rows
        ],
        "rejected_rows": [
            {
                "name": row.name,
                "raw_numbers": row.raw_numbers,
                "raw": row.raw,
                "reason": row.reason,
            }
            for row in rejected
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_nama_number_index(path: Path = NAMA_NUMBERS_JSON) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def numbers_for_devanagari_name(name: str, path: Path = NAMA_NUMBERS_JSON) -> list[int]:
    payload = load_nama_number_index(path)
    key = devanagari_key(name)
    if not key:
        return []
    for row in payload.get("rows", []):
        if row.get("key") == key:
            return [int(number) for number in row.get("numbers", [])]
    return []

