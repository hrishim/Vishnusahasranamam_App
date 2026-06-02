#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(
    r"^\s*(?:\d{1,4}\.[^\S\n]+)?"
    r"(?P<sanskrit>[\u0900-\u097F][\u0900-\u097F\s।॥:;ऽ\-]+?)"
    r"[^\S\n]+"
    r"(?P<roman>[A-Z][A-Za-zāīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ'’.-]+)"
    r"(?P<rest>[^\n]*)$"
)
ROMAN_WORD_RE = re.compile(r"[A-Za-zāīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ'’.-]+")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")
UNEXPECTED_SCRIPT_RE = re.compile(r"[\u0A80-\u0AFF\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F]")
SCRIPTURE_RE = re.compile(r"^(?:BG|MB|Mu\.?Up|Tai\.?Up|Ta\.?Up|Ka\.?Up|Vi\.?Pu|Vi|Harivamsa|Yogasiitra|YE|Arth)\.?:?$")


@dataclass(frozen=True)
class Heading:
    page: int
    line: int
    sanskrit: str
    roman: str
    text: str
    meaning: str

    @property
    def key(self) -> tuple[str, str]:
        return (compact_devanagari(self.sanskrit), roman_key(self.roman))


def compact_devanagari(text: str) -> str:
    text = re.sub(r"[^\u0900-\u097F]", "", text)
    return text.replace("ः", "").replace("ं", "")


def roman_key(text: str) -> str:
    return re.sub(r"[^A-Za-z]", "", text).casefold()


def read_pages(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def clean_meaning(line: str) -> str:
    return " ".join(line.strip().split())


def extract_headings(pages_jsonl: Path) -> list[Heading]:
    headings: list[Heading] = []
    for row in read_pages(pages_jsonl):
        lines = row["text"].splitlines()
        for idx, line in enumerate(lines):
            match = HEADING_RE.match(line)
            if not match:
                continue
            roman = match.group("roman").strip()
            if SCRIPTURE_RE.match(roman):
                continue
            if "." in roman:
                continue
            if len(roman_key(roman)) < 2:
                continue
            meaning = clean_meaning(match.group("rest"))
            lookahead = idx + 1
            while not meaning and lookahead < len(lines):
                candidate = lines[lookahead].strip()
                if not candidate:
                    lookahead += 1
                    continue
                if DEVANAGARI_RE.search(candidate):
                    break
                if ROMAN_WORD_RE.search(candidate):
                    meaning = clean_meaning(candidate)
                break
            headings.append(
                Heading(
                    page=int(row["page"]),
                    line=idx + 1,
                    sanskrit=clean_meaning(match.group("sanskrit")),
                    roman=roman,
                    text=clean_meaning(line),
                    meaning=meaning,
                )
            )
    return headings


def audit_duplicate_keys(headings: list[Heading]) -> list[str]:
    by_key: dict[tuple[str, str], list[Heading]] = defaultdict(list)
    for heading in headings:
        by_key[heading.key].append(heading)

    issues: list[str] = []
    for duplicates in by_key.values():
        if len(duplicates) < 2:
            continue
        if max(item.page for item in duplicates) - min(item.page for item in duplicates) > 1:
            continue
        meanings = {item.meaning for item in duplicates if item.meaning}
        pages = ", ".join(f"p.{item.page}: {item.text}" for item in duplicates)
        if len(meanings) > 1:
            issues.append(f"Duplicate heading with different meanings: {pages}")
    return issues


def audit_near_duplicate_romans(headings: list[Heading]) -> list[str]:
    by_roman: dict[str, list[Heading]] = defaultdict(list)
    for heading in headings:
        by_roman[heading.roman].append(heading)

    issues: list[str] = []
    for roman, items in by_roman.items():
        sanskrits = {item.sanskrit for item in items}
        if len(items) > 1 and len(sanskrits) > 1 and max(item.page for item in items) - min(item.page for item in items) <= 1:
            pages = ", ".join(f"p.{item.page}: {item.text}" for item in items)
            issues.append(f"Same Roman headword with different Sanskrit forms ({roman}): {pages}")
    return issues


def audit_required_queries(pages_jsonl: Path) -> list[str]:
    text = "\n\n".join(row["text"] for row in read_pages(pages_jsonl))
    checks = {
        "Mahayajña maps to the great yajna": "महायज्ञः Mahayajña\nThe one who is the great yajna.",
        "Mahāyajvā maps to the great sacrificer": "महायज्वा Mahāyajvā\nThe great sacrificer.",
        "Second Krtagama heading is restored": "कृतागमः Kṛtagamaḥ (655)\nThe author of the Vedas.",
        "Ananta 886 heading is restored": "अनन्तः Anantaḥ (886)\nThe limitless.",
        "Dhananjaya heading is restored": "धनञ्जयः Dhananjayah\nThe conqueror of wealth.",
        "Aja unborn heading is restored": "अजः Ajah (204, 521)\nThe unborn.",
        "Aja moving heading is restored": "अजः Ajaḥ (95, 521)\nThe one who moves.",
        "Aja Manmatha heading is restored": "अजः Ajah (95, 204)\nThe one in the form of Manmatha.",
        "Sarvesvara heading after Aja is restored": "सर्वेश्वरः Sarveśvaraḥ\nThe Lord of all.",
        "Maharha heading after Aja is restored": "महार्हः Maharhaḥ\nThe one who deserves worship.",
        "Anirdesyavapu 656 heading is restored": "अनिर्देश्यवपुः Anirdesyavapuh (656)\n\nThe one who cannot be defined categorically.",
        "Anirdesyavapu 177 heading is restored": "अनिर्देश्यवपुः Anirdesyavapuḥ (177)\n\nThe one whose form cannot be described.",
    }
    return [f"Required correction missing: {label}" for label, needle in checks.items() if needle not in text]


def audit_entry_boundaries(pages_jsonl: Path, headings: list[Heading]) -> list[str]:
    from vishnu_retrieval.search import extract_entry

    issues: list[str] = []
    checks = {
        "Mahayajña": ["महायज्ञः Mahayajña"],
        "Mahāyajvā": ["महायज्वा Mahāyajvā"],
        "अव्ययः": ["अव्ययः Avyayaḥ"],
        "Vishnu": ["विष्णुः Viṣṇuḥ"],
        "Viṣṇuḥ": ["विष्णुः Viṣṇuḥ"],
        "विष्णुः": ["विष्णुः Viṣṇuḥ"],
        "Vrsaparva": ["259; वृषपर्वा Vrsaparva"],
        "कृतागमः": ["कृतागमः Krtagamaḥ", "कृतागमः Kṛtagamaḥ"],
        "अनन्तः": ["अनन्तः Anantaḥ", "अनन्तः Anantah"],
        "अनिरदेश्यवपुः": ["अनिर्देश्यवपुः Anirdesyavapuh", "अनिर्देश्यवपुः Anirdesyavapuḥ"],
        "204. Ajaḥ (95, 521)": ["अजः Ajah", "अजः Ajaḥ"],
    }
    forbidden = {
        "Mahayajña": ["The great sacrificer."],
        "अव्ययः": ["भूतभावनः Bhūtabhāvanaḥ"],
        "Vishnu": ["वृषपर्वा Vrsaparva", "Mahejya"],
        "Viṣṇuḥ": ["वृषपर्वा Vrsaparva", "Mahejya"],
        "विष्णुः": ["वृषपर्वा Vrsaparva", "Mahejya"],
    }
    for query, prefixes in checks.items():
        hits = extract_entry(query, pages_jsonl, window_after=5)
        if not hits:
            issues.append(f"No entry returned for regression query {query!r}")
            continue
        for hit in hits:
            first_line = hit.text.splitlines()[0].strip()
            if not any(first_line.startswith(prefix) for prefix in prefixes):
                issues.append(f"Regression query {query!r} returned unrelated heading: {first_line!r}")
        combined = "\n\n".join(hit.text for hit in hits)
        if query == "कृतागमः":
            first_lines = {hit.text.splitlines()[0].strip() for hit in hits}
            if not {"कृतागमः Krtagamaḥ (789)", "कृतागमः Kṛtagamaḥ (655)"}.issubset(first_lines):
                issues.append(f"Regression query {query!r} did not return both Krtagama entries")
        if query == "अनन्तः":
            first_lines = {hit.text.splitlines()[0].strip() for hit in hits}
            if not {"अनन्तः Anantaḥ (886)", "अनन्तः Anantah (659)"}.issubset(first_lines):
                issues.append(f"Regression query {query!r} did not return both Ananta entries")
            for hit in hits:
                if hit.text.startswith("अनन्तः Anantaḥ (886)") and "धनञ्जयः Dhananjayah" in hit.text:
                    issues.append(f"Regression query {query!r} included the next Dhananjaya entry")
        if query == "अनिरदेश्यवपुः":
            first_lines = {hit.text.splitlines()[0].strip() for hit in hits}
            required = {"अनिर्देश्यवपुः Anirdesyavapuh (656)", "अनिर्देश्यवपुः Anirdesyavapuḥ (177)"}
            if not required.issubset(first_lines):
                issues.append(f"Regression query {query!r} did not return both Anirdesyavapu entries")
        if query == "204. Ajaḥ (95, 521)":
            first_lines = {hit.text.splitlines()[0].strip() for hit in hits}
            required = {"अजः Ajah (204, 521)", "अजः Ajaḥ (95, 521)", "अजः Ajah (95, 204)"}
            if not required.issubset(first_lines):
                issues.append(f"Regression query {query!r} did not return all Aja entries")
            neighbor_names = ("सर्वेश्वरः Sarveśvaraḥ", "दुर्मर्षणः Durmarṣaṇaḥ", "महार्हः Maharhaḥ")
            for hit in hits:
                if hit.text.splitlines()[0].strip() in required and any(name in hit.text for name in neighbor_names):
                    issues.append(f"Regression query {query!r} included a neighboring entry")
        for needle in forbidden.get(query, []):
            if needle in combined:
                issues.append(f"Regression query {query!r} included forbidden unrelated text: {needle!r}")
    return issues


def audit_repeated_headword_extraction(pages_jsonl: Path, headings: list[Heading]) -> list[str]:
    from vishnu_retrieval.search import devanagari_match_key, extract_entry

    by_key: dict[str, list[Heading]] = defaultdict(list)
    for heading in headings:
        key = devanagari_match_key(heading.sanskrit).rstrip("ः")
        if key:
            by_key[key].append(heading)

    issues: list[str] = []
    for duplicates in by_key.values():
        if len(duplicates) < 2:
            continue
        query = duplicates[0].sanskrit.replace(":", "ः")
        hits = extract_entry(query, pages_jsonl=pages_jsonl, window_after=5)
        returned = {hit.text.splitlines()[0].strip() for hit in hits}
        missing = [heading.text for heading in duplicates if heading.text not in returned]
        if missing:
            missing_text = "; ".join(missing)
            returned_text = "; ".join(sorted(returned))
            issues.append(
                f"Repeated headword query {query!r} missed heading(s): {missing_text}. Returned: {returned_text}"
            )
    return issues


def audit_all_heading_extraction(pages_jsonl: Path, headings: list[Heading]) -> list[str]:
    from vishnu_retrieval.search import extract_entry, heading_matches_query, parse_nama_heading

    issues: list[str] = []
    for heading in headings:
        if not parse_nama_heading(heading.text):
            continue
        query = heading.sanskrit.replace(":", "ः")
        hits = extract_entry(query, pages_jsonl=pages_jsonl, window_after=5)
        first_lines = [hit.text.splitlines()[0].strip() if hit.text.splitlines() else "" for hit in hits]
        if heading.text not in first_lines:
            returned = "; ".join(first_lines[:8])
            issues.append(
                f"Full-heading query {query!r} missed p.{heading.page} heading {heading.text!r}. Returned: {returned}"
            )
            continue

        for hit in hits:
            lines = [line.strip() for line in hit.text.splitlines() if line.strip()]
            if not lines:
                continue
            if not heading_matches_query(lines[0], query):
                issues.append(f"Full-heading query {query!r} returned wrong starting heading: {lines[0]!r}")
            for line in lines[1:]:
                if parse_nama_heading(line) and not heading_matches_query(line, query):
                    issues.append(f"Full-heading query {query!r} included neighboring heading: {line!r}")
                    break
    return issues


def audit_sloka_script_quality(pages_jsonl: Path) -> list[str]:
    from vishnu_retrieval.io import read_pages
    from vishnu_retrieval.search import sloka_blocks

    issues: list[str] = []
    for page in read_pages(pages_jsonl):
        for _, _, block in sloka_blocks(page.text):
            for line in block.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                latin_inside_devanagari = bool(
                    re.search(r"[\u0900-\u097F][A-Za-z]|[A-Za-z][\u0900-\u097F]", stripped)
                )
                latin_between_devanagari = bool(
                    re.search(r"[\u0900-\u097F][^\n]*\s[A-Za-z]{4,}\s[^\n]*[\u0900-\u097F]", stripped)
                )
                if latin_inside_devanagari or latin_between_devanagari:
                    issues.append(f"Sloka on p.{page.page} mixes Devanagari and Latin text: {stripped!r}")
                if UNEXPECTED_SCRIPT_RE.search(stripped):
                    issues.append(f"Sloka on p.{page.page} contains unexpected Indic script characters: {stripped!r}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit extracted Vishnusahasranamam entry headings.")
    parser.add_argument("--pages", default="data/ocr/pages.jsonl")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    pages_jsonl = Path(args.pages)
    headings = extract_headings(pages_jsonl)
    warnings = []
    warnings.extend(audit_duplicate_keys(headings))
    warnings.extend(audit_near_duplicate_romans(headings))
    issues = []
    issues.extend(audit_required_queries(pages_jsonl))
    issues.extend(audit_entry_boundaries(pages_jsonl, headings))
    issues.extend(audit_repeated_headword_extraction(pages_jsonl, headings))
    issues.extend(audit_all_heading_extraction(pages_jsonl, headings))
    issues.extend(audit_sloka_script_quality(pages_jsonl))

    payload = {
        "pages_file": str(pages_jsonl),
        "heading_count": len(headings),
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Entry headings found: {payload['heading_count']}")
        print(f"Issues found: {payload['issue_count']}")
        for issue in issues:
            print(f"- {issue}")
        print(f"Warnings found: {payload['warning_count']}")
        for warning in warnings:
            print(f"- {warning}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
