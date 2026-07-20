from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.desktop_app import display_text_to_html, render_entry


OUT = Path("outputs/clean_doc_check/rendered_formatting_audit.md")

PAGE_FOOTER_RE = re.compile(r"^\s*(?:VISNUSAHASRANAMA|VIṢṆUSAHASRANAMA|\d+\s*\|\s*VI)", re.IGNORECASE)
ENTRY_HEADING_RE = re.compile(r"^Entry\s+\d+\s+-\s+Nama:\s+\d+")
BAD_HEADING_RE = re.compile(r"^\s*(?:Axt|Ast|Txt|HATTA|WY|HAM|Hert|Held)\s*:", re.IGNORECASE)
ENGLISH_IN_TRANSLIT_RE = re.compile(
    r"\b(the|one|who|word|means|lord|being|because|since|therefore|where|when|which|this|that|with|from|into|if|then|does|not|know|continues|form|other|until|every|called|there|are|is|as|it|he|she|you|we|they|their|his|her|and|or|to|by|for|on)\b",
    re.IGNORECASE,
)


@dataclass
class FormatIssue:
    number: int
    reason: str
    context: str


def context_for(lines: list[str], index: int) -> str:
    start = max(0, index - 2)
    end = min(len(lines), index + 3)
    return " / ".join(line.strip() for line in lines[start:end] if line.strip()).replace("|", "/")


def line_issues(number: int, text: str) -> list[FormatIssue]:
    issues: list[FormatIssue] = []
    lines = text.splitlines()
    if not lines or not ENTRY_HEADING_RE.match(lines[0]):
        issues.append(FormatIssue(number, "Result does not start with an Entry/Nama heading.", lines[0] if lines else ""))
    if text != text.strip():
        issues.append(FormatIssue(number, "Result has leading or trailing whitespace.", ""))
    for index, line in enumerate(lines):
        if line.rstrip() != line:
            issues.append(FormatIssue(number, "Line has trailing whitespace.", context_for(lines, index)))
        if PAGE_FOOTER_RE.match(line):
            issues.append(FormatIssue(number, "Page footer/header leaked into rendered output.", context_for(lines, index)))
        if BAD_HEADING_RE.match(line):
            issues.append(FormatIssue(number, "OCR garbage heading leaked into rendered output.", context_for(lines, index)))
    return issues


def html_issues(number: int, text: str) -> list[FormatIssue]:
    issues: list[FormatIssue] = []
    html = display_text_to_html(text)
    if "<h2>" not in html:
        issues.append(FormatIssue(number, "Rendered HTML has no entry heading.", html[:140]))
    if "<p class=\"para\"></p>" in html or "<h2></h2>" in html or "<h3></h3>" in html:
        issues.append(FormatIssue(number, "Rendered HTML contains an empty visible block.", html[:200]))
    if "Axt:" in html:
        issues.append(FormatIssue(number, "Rendered HTML still contains Axt artifact.", html[:200]))
    for match in re.finditer(r'<div class="translit">([^<]+)</div>', html):
        translit_text = match.group(1)
        if ENGLISH_IN_TRANSLIT_RE.search(translit_text):
            issues.append(FormatIssue(number, "English sentence styled as transliteration.", translit_text[:220]))
    return issues


def main() -> int:
    issues: list[FormatIssue] = []
    rows = load_canonical_namas()
    for row in rows:
        number = int(row["number"])
        result = render_entry(str(row.get("roman") or row.get("devanagari") or number), top_k=1)
        text = result.display_text
        issues.extend(line_issues(number, text))
        issues.extend(html_issues(number, text))

    lines = [
        "# Rendered Formatting Audit",
        "",
        f"Entries checked: {len(rows)}",
        f"Formatting issues found: {len(issues)}",
        "",
        "| Entry | Reason | Context |",
        "|---:|---|---|",
    ]
    for issue in issues[:500]:
        lines.append(f"| {issue.number} | {issue.reason} | {issue.context} |")
    if len(issues) > 500:
        lines.append(f"|  | ... {len(issues) - 500} more |  |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(f"formatting_issues={len(issues)}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
