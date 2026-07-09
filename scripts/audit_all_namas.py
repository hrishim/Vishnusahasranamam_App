from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.io import read_pages
from vishnu_retrieval.search import extract_entry, extract_entry_by_number, roman_match_key


OUT = Path("outputs/clean_doc_check/all_namas_audit.md")
HEADING_RE = re.compile(r"^\s*(?P<num>(?:\d\s*){0,4})\s*[.;]\s*(?P<title>.+?)\s*$")
NON_NAME_WORDS = {
    "for",
    "to",
    "and",
    "or",
    "the",
    "this",
    "that",
    "from",
    "with",
    "without",
    "because",
    "i",
    "illusion",
    "inability",
    "buffet",
    "misunderstanding",
    "generally",
}


@dataclass
class Heading:
    raw_num: int | None
    title: str
    page: int
    line: int
    raw_line: str
    inferred_num: int | None = None


def clean_title(title: str) -> str:
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    title = re.sub(r"\s+", " ", title)
    return title


def looks_like_name(title: str) -> bool:
    title = clean_title(title)
    if not title or len(title) > 90:
        return False
    if any(mark in title for mark in "।॥|,:"):
        return False
    words = re.findall(r"[A-Za-zāīūṛṝḷḹṅñṭḍṇśṣḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢḤ]+", title)
    if not words:
        return False
    if len(words) > 5:
        return False
    if words[0].casefold() in NON_NAME_WORDS:
        return False
    return True


def collect_headings() -> list[Heading]:
    headings: list[Heading] = []
    for page in read_pages():
        for line_no, line in enumerate(page.text.splitlines(), 1):
            match = HEADING_RE.match(line)
            if not match:
                continue
            raw_text = re.sub(r"\s+", "", match.group("num"))
            raw_num = int(raw_text) if raw_text else None
            title = clean_title(match.group("title"))
            if not looks_like_name(title):
                continue
            headings.append(Heading(raw_num, title, page.page, line_no, line.strip()))
    return headings


def infer_sequence(headings: list[Heading]) -> list[Heading]:
    expected = 1
    for heading in headings:
        raw = heading.raw_num
        if raw is None:
            heading.inferred_num = expected
            expected += 1
            continue
        candidates = [raw]
        if raw < expected:
            expected_text = str(expected)
            raw_text = str(raw)
            if (
                expected_text.endswith(raw_text)
                or expected_text.startswith(raw_text)
                or raw == expected % 10
                or raw == expected % 100
            ):
                candidates.insert(0, expected)
        if raw == expected:
            heading.inferred_num = raw
            expected += 1
        elif candidates[0] == expected:
            heading.inferred_num = expected
            expected += 1
        elif raw > expected and raw <= 1000:
            heading.inferred_num = raw
            expected = raw + 1
        elif raw <= 1000:
            heading.inferred_num = expected
            expected += 1
    return headings


def retrieval_check(title: str) -> tuple[bool, str]:
    query = clean_title(title).split()[0]
    if not query:
        return False, ""
    hits = extract_entry(query)
    if not hits:
        return False, query
    query_key = roman_match_key(query)
    for hit in hits:
        first = hit.text.splitlines()[0] if hit.text.splitlines() else ""
        if query_key and query_key in roman_match_key(first):
            return True, query
    return False, query


def main() -> None:
    headings = infer_sequence(collect_headings())
    by_inferred = {h.inferred_num: h for h in headings if h.inferred_num is not None and 1 <= h.inferred_num <= 1000}
    counts = Counter(h.inferred_num for h in headings if h.inferred_num is not None)
    missing = [n for n in range(1, 1001) if n not in by_inferred]
    duplicates = [(n, c) for n, c in sorted(counts.items()) if c > 1 and n is not None]

    retrieval_failures: list[tuple[int, Heading, str]] = []
    retrieval_pass = 0
    for n in range(1, 1001):
        heading = by_inferred.get(n)
        if not heading:
            continue
        ok, query = retrieval_check(heading.title)
        if ok:
            retrieval_pass += 1
        else:
            retrieval_failures.append((n, heading, query))

    number_failures: list[int] = []
    for n in range(1, 1001):
        if not extract_entry_by_number(n):
            number_failures.append(n)

    canonical_search_failures: list[tuple[int, str]] = []
    for row in load_canonical_namas():
        number = int(row.get("number", 0))
        query = str(row.get("roman", "")).strip() or str(row.get("devanagari", "")).strip()
        if not query:
            canonical_search_failures.append((number, ""))
            continue
        if not extract_entry(query):
            canonical_search_failures.append((number, query))

    lines: list[str] = []
    lines.append("# All 1000 Nama Audit")
    lines.append("")
    lines.append(f"Candidate heading lines found: {len(headings):,}")
    lines.append(f"Unique inferred nama numbers: {len(by_inferred):,} / 1000")
    lines.append(f"Missing inferred nama numbers: {len(missing):,}")
    lines.append(f"Duplicate inferred nama numbers: {len(duplicates):,}")
    lines.append(f"Full-entry retrieval pass: {retrieval_pass:,} / {len(by_inferred):,} parsed headings")
    lines.append(f"Full-entry retrieval failures: {len(retrieval_failures):,}")
    lines.append(f"Number extraction failures: {len(number_failures):,}")
    lines.append(f"Canonical-name search failures: {len(canonical_search_failures):,}")
    lines.append("")
    lines.append("## Missing Numbers")
    lines.append("")
    lines.append(", ".join(str(n) for n in missing) if missing else "None.")
    lines.append("")
    lines.append("## Duplicate Inferred Numbers")
    lines.append("")
    if duplicates:
        for n, c in duplicates[:100]:
            lines.append(f"- {n}: {c} candidates")
    else:
        lines.append("None.")
    lines.append("")
    lines.append("## Parsed Headings")
    lines.append("")
    lines.append("| No. | Raw No. | Page | Title |")
    lines.append("|---:|---:|---:|---|")
    for n in range(1, 1001):
        h = by_inferred.get(n)
        if h:
            lines.append(f"| {n} | {h.raw_num} | {h.page} | {h.title.replace('|', '\\|')} |")
        else:
            lines.append(f"| {n} |  |  | MISSING |")
    lines.append("")
    lines.append("## Retrieval Failures")
    lines.append("")
    if retrieval_failures:
        for n, h, query in retrieval_failures[:200]:
            lines.append(f"- {n} p.{h.page}: query `{query}` did not return heading `{h.title}`")
        if len(retrieval_failures) > 200:
            lines.append(f"- ... {len(retrieval_failures) - 200:,} more")
    else:
        lines.append("None.")
    lines.append("")
    lines.append("## Number Extraction Failures")
    lines.append("")
    lines.append(", ".join(str(n) for n in number_failures) if number_failures else "None.")
    lines.append("")
    lines.append("## Canonical Search Failures")
    lines.append("")
    if canonical_search_failures:
        for n, query in canonical_search_failures[:200]:
            lines.append(f"- {n}: `{query}`")
        if len(canonical_search_failures) > 200:
            lines.append(f"- ... {len(canonical_search_failures) - 200:,} more")
    else:
        lines.append("None.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(
        f"unique={len(by_inferred)} missing={len(missing)} "
        f"retrieval_failures={len(retrieval_failures)} "
        f"number_failures={len(number_failures)} canonical_search_failures={len(canonical_search_failures)}"
    )


if __name__ == "__main__":
    main()
