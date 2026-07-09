from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.desktop_app import render_entry
from vishnu_retrieval.search import devanagari_match_key, roman_match_key


OUT_MD = Path("outputs/clean_doc_check/app_name_search_audit.md")
OUT_CSV = Path("outputs/clean_doc_check/app_name_search_audit.csv")


@dataclass
class QueryAudit:
    number: int
    devanagari: str
    roman: str
    query_kind: str
    query: str
    passed: bool
    issues: list[str]
    matched_entry_numbers: list[int]
    preview: str


def entry_blocks(display_text: str) -> list[str]:
    if not display_text or display_text.strip() == "No full entry found.":
        return []
    starts = [match.start() for match in re.finditer(r"(?m)^Entry \d+(?:\s+-[^\n]*)?", display_text)]
    if not starts:
        return [display_text]
    starts.append(len(display_text))
    return [display_text[starts[i] : starts[i + 1]].strip() for i in range(len(starts) - 1)]


def header_numbers(block: str) -> set[int]:
    first_line = block.splitlines()[0] if block.splitlines() else ""
    numbers = {int(value) for value in re.findall(r"\b(?:Nama:\s*)?(\d{1,4})\b", first_line) if 1 <= int(value) <= 1000}
    for line in block.splitlines()[1:5]:
        for value in re.findall(r"\((\d{1,4})\)", line):
            number = int(value)
            if 1 <= number <= 1000:
                numbers.add(number)
    return numbers


def block_contains_expected_heading(block: str, number: int, devanagari: str, roman: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    expected_dev = devanagari_match_key(devanagari)
    expected_roman = roman_match_key(roman)
    for line in lines[:8]:
        if f"({number})" not in line:
            continue
        line_dev = devanagari_match_key(line)
        line_roman = roman_match_key(line)
        if expected_dev and expected_dev in line_dev:
            return True
        if expected_roman and expected_roman in line_roman:
            return True
    return False


def audit_query(number: int, devanagari: str, roman: str, query_kind: str, query: str) -> QueryAudit:
    result = render_entry(query)
    issues: list[str] = []
    blocks = entry_blocks(result.display_text)
    matched_numbers: list[int] = []
    exact_match = False
    for block in blocks:
        numbers = header_numbers(block)
        if number in numbers:
            matched_numbers.append(number)
            if block_contains_expected_heading(block, number, devanagari, roman):
                exact_match = True

    if not blocks:
        issues.append("No full entry found.")
    if number not in matched_numbers:
        returned = sorted({n for block in blocks for n in header_numbers(block)})
        issues.append(
            "Expected nama number was not returned."
            + (f" Returned numbers: {', '.join(str(n) for n in returned[:20])}." if returned else "")
        )
    if matched_numbers and not exact_match:
        issues.append("Expected number appeared, but the visible heading did not match the canonical name.")
    if roman and roman_match_key(roman) in roman_match_key(result.display_text.splitlines()[0] if result.display_text.splitlines() else ""):
        issues.append("IAST appeared in the Entry header line.")

    preview = "\n".join(result.display_text.splitlines()[:14]).strip()
    return QueryAudit(
        number=number,
        devanagari=devanagari,
        roman=roman,
        query_kind=query_kind,
        query=query,
        passed=not issues,
        issues=issues,
        matched_entry_numbers=matched_numbers,
        preview=preview,
    )


def main() -> int:
    audits: list[QueryAudit] = []
    for row in load_canonical_namas():
        number = int(row["number"])
        devanagari = str(row.get("devanagari", "")).strip()
        roman = str(row.get("roman", "")).strip()
        if devanagari:
            audits.append(audit_query(number, devanagari, roman, "Devanagari", devanagari))
        else:
            audits.append(
                QueryAudit(number, devanagari, roman, "Devanagari", "", False, ["No canonical Devanagari query."], [], "")
            )
        if roman:
            audits.append(audit_query(number, devanagari, roman, "Roman", roman))
        else:
            audits.append(QueryAudit(number, devanagari, roman, "Roman", "", False, ["No canonical Roman query."], [], ""))

    failed = [audit for audit in audits if not audit.passed]
    failed_numbers = sorted({audit.number for audit in failed})
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "number",
                "devanagari",
                "roman",
                "query_kind",
                "query",
                "passed",
                "issues",
                "matched_entry_numbers",
            ],
        )
        writer.writeheader()
        for audit in audits:
            writer.writerow(
                {
                    "number": audit.number,
                    "devanagari": audit.devanagari,
                    "roman": audit.roman,
                    "query_kind": audit.query_kind,
                    "query": audit.query,
                    "passed": "yes" if audit.passed else "no",
                    "issues": " | ".join(audit.issues),
                    "matched_entry_numbers": ", ".join(str(n) for n in audit.matched_entry_numbers),
                }
            )

    lines: list[str] = [
        "# Mac App Name Search Audit",
        "",
        "This calls the same Name Search rendering path used by the Mac app.",
        "",
        f"Canonical namas checked: {len(load_canonical_namas())}",
        f"Queries checked: {len(audits)}",
        f"Passed queries: {len(audits) - len(failed)}",
        f"Failed queries: {len(failed)}",
        f"Namas with at least one failed query: {len(failed_numbers)}",
        "",
        "## Failed Queries",
        "",
    ]
    if not failed:
        lines.append("None.")
    else:
        lines.extend(["| No. | Nama | Query | Issues |", "|---:|---|---|---|"])
        for audit in failed:
            issues = "<br>".join(issue.replace("|", "\\|") for issue in audit.issues)
            lines.append(
                f"| {audit.number} | {audit.devanagari} {audit.roman} | "
                f"{audit.query_kind}: `{audit.query.replace('|', '\\|')}` | {issues} |"
            )
        lines.append("")
        for audit in failed[:100]:
            lines.append(f"## {audit.number}. {audit.devanagari} {audit.roman} - {audit.query_kind}")
            lines.append("")
            lines.extend(f"- {issue}" for issue in audit.issues)
            lines.append("")
            lines.append("```text")
            lines.append(audit.preview)
            lines.append("```")
            lines.append("")
        if len(failed) > 100:
            lines.append(f"... {len(failed) - 100} more failed queries are listed in the CSV.")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(OUT_MD)
    print(OUT_CSV)
    print(f"queries={len(audits)} failed={len(failed)} failed_namas={len(failed_numbers)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
