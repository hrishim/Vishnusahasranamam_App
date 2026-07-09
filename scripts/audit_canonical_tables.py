from __future__ import annotations

import csv
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


CANONICAL_JSON = Path("data/index/canonical_namas.json")
CSV_TABLES = [
    Path("outputs/clean_doc_check/canonical_namas_table.csv"),
    Path("outputs/clean_doc_check/canonical_namas_iast_table.csv"),
]
OUT = Path("outputs/clean_doc_check/canonical_tables_audit.md")


DEVANAGARI_LETTER_RE = re.compile(r"[\u0900-\u0963]")


def roman_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = (
        text.replace("ṁ", "m")
        .replace("ṃ", "m")
        .replace("ś", "s")
        .replace("ṣ", "s")
        .replace("ḥ", "h")
        .replace("ṛ", "r")
    )
    return re.sub(r"[^a-z]", "", text)


def load_json_rows() -> list[dict]:
    return json.loads(CANONICAL_JSON.read_text(encoding="utf-8")).get("namas", [])


def load_csv_rows(path: Path) -> dict[int, list[str]]:
    if not path.exists():
        return {}
    rows: dict[int, list[str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if row and row[0].isdigit():
                rows[int(row[0])] = row
    return rows


def row_issues(row: dict, csv_rows: dict[str, dict[int, list[str]]]) -> list[str]:
    issues: list[str] = []
    number = int(row.get("number", 0))
    devanagari = str(row.get("devanagari", ""))
    key = str(row.get("key", ""))
    roman = str(row.get("roman", ""))
    source_title = str(row.get("source_title", ""))
    dev_count = len(DEVANAGARI_LETTER_RE.findall(devanagari))
    if dev_count < 2:
        issues.append("Devanagari name is missing, too short, or punctuation-only.")
    if key and key != re.sub(r"[^\u0900-\u097F]", "", devanagari):
        issues.append("JSON key does not match Devanagari field.")
    roman_from_dev = roman_key(roman)
    roman_from_source = roman_key(source_title)
    if roman_from_dev and roman_from_source:
        source_allows_option = roman_from_dev in roman_from_source or roman_from_source in roman_from_dev
        similarity = SequenceMatcher(None, roman_from_dev, roman_from_source).ratio()
        if not source_allows_option and similarity < 0.82:
            issues.append(f"Roman/heading mismatch: `{roman}` vs source `{source_title}`.")
    for name, rows in csv_rows.items():
        csv_row = rows.get(number)
        if not csv_row:
            issues.append(f"{name} is missing row {number}.")
            continue
        if len(csv_row) > 1 and csv_row[1] != devanagari:
            issues.append(f"{name} Devanagari differs: `{csv_row[1]}`.")
        if len(csv_row) > 2 and csv_row[2] != roman:
            issues.append(f"{name} IAST differs: `{csv_row[2]}`.")
    return issues


def main() -> int:
    rows = load_json_rows()
    csv_rows = {path.name: load_csv_rows(path) for path in CSV_TABLES}
    flagged: list[tuple[dict, list[str]]] = []
    numbers = [int(row.get("number", 0)) for row in rows]
    if len(rows) != 1000 or sorted(numbers) != list(range(1, 1001)):
        flagged.append(({"number": 0, "devanagari": "TABLE", "roman": "", "source_title": ""}, ["JSON does not contain exactly numbers 1-1000."]))
    for row in rows:
        issues = row_issues(row, csv_rows)
        if issues:
            flagged.append((row, issues))

    lines = [
        "# Canonical Tables Audit",
        "",
        f"JSON rows: {len(rows)}",
        f"Flagged rows: {len(flagged)}",
        "",
        "| No. | Devanagari | Roman | Source heading | Issues |",
        "|---:|---|---|---|---|",
    ]
    for row, issues in flagged:
        lines.append(
            f"| {row.get('number')} | `{row.get('devanagari', '')}` | `{row.get('roman', '')}` | "
            f"`{row.get('source_title', '')}` | {'<br>'.join(issues)} |"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(f"rows={len(rows)} flagged={len(flagged)}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
