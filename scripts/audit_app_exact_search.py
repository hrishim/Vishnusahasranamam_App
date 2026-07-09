from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.desktop_app import render_exact
from vishnu_retrieval.search import devanagari_match_key, roman_match_key


OUT_MD = Path("outputs/clean_doc_check/app_exact_search_audit.md")
OUT_CSV = Path("outputs/clean_doc_check/app_exact_search_audit.csv")

SUSPICIOUS_PATTERNS = {
    r"\bG\s+tā\b": "Gita/Gītā spacing error",
    r"\bbha\s+tyā\b": "bhaktya spacing error",
    r"\burlabha\b": "missing initial d in durlabha",
    r"\burati\s+rama\b": "missing letters in Duratikrama",
    r"\blook\s+s\b": "broken English word",
    r"\bconse\s+uences\b": "broken English word",
    r"\bnowledge\b": "missing k in knowledge",
    r"\buestion\b": "missing q in question",
    r"\buic\s+to\s+anger\b": "missing q in quick",
    r"\buic\s+ly\b": "broken quickly",
    r"\batttibute\b": "extra t in attribute",
    r"\bneeds\s+to\s+done\b": "missing be",
    r"\bBrahmanand\b": "missing space in Brahman and",
    r"\bupto\b": "missing space in up to",
    r"\biskyoga\b": "missing space in is yoga",
}


@dataclass
class ExactAudit:
    number: int
    devanagari: str
    roman: str
    query_kind: str
    query: str
    passed: bool
    issues: list[str]
    preview: str


def entry_blocks(display_text: str) -> list[str]:
    starts = [match.start() for match in re.finditer(r"(?m)^Entry \d+(?:\s+-[^\n]*)?", display_text)]
    if not starts:
        return []
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


def output_has_verified_entry(output: str, number: int, devanagari: str) -> bool:
    expected_dev = devanagari_match_key(devanagari)
    for block in entry_blocks(output):
        if number not in header_numbers(block):
            continue
        if not expected_dev:
            return True
        for line in block.splitlines()[1:6]:
            if expected_dev in devanagari_match_key(line):
                return True
    return False


def query_found_in_output(query: str, query_kind: str, output: str) -> bool:
    if query_kind == "Devanagari":
        q_key = devanagari_match_key(query)
        out_key = devanagari_match_key(output)
        if not q_key:
            return False
        return q_key in out_key or q_key.rstrip("ः") in out_key
    q_key = roman_match_key(query)
    out_key = roman_match_key(output)
    return bool(q_key and q_key in out_key)


def full_output_issues(output: str) -> list[str]:
    issues: list[str] = []
    for pattern, reason in SUSPICIOUS_PATTERNS.items():
        if re.search(pattern, output):
            issues.append(f"Suspicious full-output pattern `{pattern}`: {reason}.")
    return issues


def audit_query(number: int, devanagari: str, roman: str, query_kind: str, query: str) -> ExactAudit:
    result = render_exact(query)
    output = result.display_text
    issues: list[str] = []
    if not query:
        issues.append(f"No canonical {query_kind} query.")
    elif output.strip() == "No exact matches found.":
        issues.append("No exact match found.")
    elif not query_found_in_output(query, query_kind, output) and not output_has_verified_entry(output, number, devanagari):
        issues.append("Exact output did not contain the searched name after normalization.")
    issues.extend(full_output_issues(output))
    preview = "\n".join(output.splitlines()[:14]).strip()
    return ExactAudit(number, devanagari, roman, query_kind, query, not issues, issues, preview)


def main() -> int:
    audits: list[ExactAudit] = []
    for row in load_canonical_namas():
        number = int(row["number"])
        devanagari = str(row.get("devanagari", "")).strip()
        roman = str(row.get("roman", "")).strip()
        audits.append(audit_query(number, devanagari, roman, "Devanagari", devanagari))
        audits.append(audit_query(number, devanagari, roman, "Roman", roman))

    failed = [audit for audit in audits if not audit.passed]
    failed_numbers = sorted({audit.number for audit in failed})
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["number", "devanagari", "roman", "query_kind", "query", "passed", "issues"],
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
                }
            )

    lines: list[str] = [
        "# Mac App Exact Text Audit",
        "",
        "This calls the same Exact Text rendering path used by the Mac app.",
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
