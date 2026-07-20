from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.desktop_app import entry_body_with_clean_heading
from vishnu_retrieval.search import extract_entry_by_number, roman_match_key


OUT = Path("outputs/clean_doc_check/rendered_entries_quality_audit.md")
FULL_OUT = Path("outputs/clean_doc_check/rendered_entries_quality_full.md")
OCR_STUDIO_SOURCE = Path("outputs/pdf_ocr_studio_sources/Vishnusahasranamam_PDF_OCR_Studio_corrected_vol_01_05.docx")

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")
BROKEN_SPACING_RE = re.compile(r"\b[a-zA-ZāīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ]\s+[a-zāīūṛṝḷṅñṭḍṇśṣḥ]\b")
SUSPICIOUS_PATTERNS = {
    r"\bAxt\s*:": "OCR garbage heading marker",
    r"\b(?:aṣṭā|Spaṣṭā|Spaṣṭa-a)\s+ṣara\b": "broken akṣara word",
    r"\bdoes not now\b": "missing k in know",
    r"\bNārāyana\b": "damaged Nārāyaṇa",
    r"\bākāṣa\b": "damaged ākāśa",
    r"\bŚa\s+ara\b": "damaged Śaṅkara",
    r"नािायण": "damaged नारायण Devanagari",
    r"\bsatyasa\s+alpa\b": "damaged satyasaṅkalpa",
    r"\bSiddhasa\s+alpa\b": "damaged Siddhasaṅkalpa",
    r"\bthis ind of\b": "missing k in kind",
    r"\bthe urāṇas\b": "missing P in Purāṇas",
    r"\bGodess\b": "misspelled Goddess",
    r"Viṣִִṇupurāִṇa": "damaged Viṣṇupurāṇa",
    r"‘ now Vyāsa": "missing K in Know Vyāsa",
    r"Puṇḍar\s+ā\s+ṣa": "damaged Puṇḍarīkākṣa",
    r"Vyāsa\s+‘s": "bad possessive spacing",
    r"\bre establish\b": "missing hyphen in re-establish",
    r"कृ ष्णेः": "split Kṛṣṇa Devanagari",
    r"\bG\s+tā\b": "Gita/Gītā spacing error",
    r"\bbha\s+tyā\b": "bhaktya spacing error",
    r"\burlabha\b": "missing initial d in durlabha",
    r"\blook\s+s\b": "broken English word",
    r"\bconse\s+uences\b": "broken English word",
    r"\bnown\b": "missing k in known",
    r"\bnowledge\b": "missing k in knowledge",
    r"\buestion\b": "missing q in question",
    r"\bIgvara\b|\bJévara\b|\bIvara\b|\b75८": "Ishvara/Isvara OCR error",
    r"\bBhagava@n\b": "Bhagavan OCR error",
    r"\burati\s+rama\b": "missing letters in Duratikrama",
    r"\b(?:arrives|arrive|arrived|arriving)\s+atka\b|\batka\s+(?:time|situation|certain|joke)\b": "broken 'at a'",
    r"\b\w+kyou\b|\b\w+kyears\b": "glued OCR k before English word",
    r"\bthin(?=\s+(?:of|about|that|I|‘|\"))": "missing k in think",
    r"\bee[p]?s\b": "missing k in keeps",
    r"\buic\s+to\s+anger\b": "missing q in quick",
    r"\bwork\s+s\b": "broken works",
    r"\bo\s+ay\b": "broken okay",
    r"\bSoemtimes\b": "misspelled Sometimes",
    r"\bthinkk+(?:ing)?\b": "extra k in think",
    r"\bexceeed\b": "extra e in exceed",
    r"\bqqquiet(?:ly|er)?\b": "extra q in quiet",
    r"\bdddon[’']t\b": "extra d in don't",
    r"\bkkkk?karma\b": "extra k in karma",
    r"\batttibute\b": "extra t in attribute",
    r"\batka\s+situation\b": "broken 'at a situation'",
    r"\buarters?\b": "missing q in quarter",
    r"\buic\s+ly\b": "broken quickly",
    r"\b[Aa]tleast\b": "broken At least",
    r"\bneeds\s+to\s+done\b": "missing be",
    r"\bBrahmanand\b": "missing space in Brahman and",
    r"\bupto\b": "missing space in up to",
    r"\biskyoga\b": "missing space in is yoga",
    r"\bKr\s+ṣṇa\b": "broken Krishna transliteration",
    r"\bLa\s+ṣmī\b": "broken Lakshmi transliteration",
    r"\bvi\s+va\w*\b|\bVi\s+va\w*\b": "broken vishva transliteration",
    r"\bBhagav\s+n\b": "broken Bhagavan transliteration",
    r"\bPP+rahlāda\b": "damaged Prahlāda",
    r"\bDD+evadutta\b": "damaged Devadutta",
    r"\bAgni,the\b": "missing space after comma",
    r"\bdevotes\.\s*arigraha\b": "damaged devotees/Parigraha sentence",
    r"\bhance he is called\b": "damaged hence He",
    r"\bpuṇyaśravaṇa\s+rtana\b": "damaged puṇyaśravaṇa-kīrtana",
    r"\bK\s+rtana\b": "damaged Kīrtana",
    r"\brtana,\s+singing\b": "damaged kīrtana",
    r"\brtana\.\s+Īśvara\b": "damaged kīrtana",
    r"\bVāsudevaas\b": "missing space after Vāsudeva",
    r"\bisVāsudeva\b": "missing space before Vāsudeva",
    r"\bthekṣetra\b": "missing space before kṣetra",
    r"\bphilosoper\b": "misspelled philosopher",
    r"\bself-\s+consciousness\b": "broken self-consciousness",
    r"\bself-\s+judgement\b": "broken self-judgement",
    r"\bself loath\b": "damaged self-loathing",
    r"\bknowledge-\s+wise\b": "broken knowledge-wise",
}


@dataclass
class EntryAudit:
    number: int
    devanagari: str
    roman: str
    page: int | None
    text: str
    issues: list[str]


def visible_entry_for_number(number: int) -> tuple[str, int | None]:
    hits = extract_entry_by_number(number, window_after=5)
    if not hits:
        return "", None
    return entry_body_with_clean_heading(hits[0]), hits[0].page_start


def load_source_derivations() -> dict[str, list[str]]:
    if not OCR_STUDIO_SOURCE.exists():
        return {}
    text = subprocess.check_output(["textutil", "-convert", "txt", "-stdout", str(OCR_STUDIO_SOURCE)], text=True)
    lines = [line.strip() for line in text.replace("\u2028", "\n").replace("\f", "\n").splitlines()]
    derivations: dict[str, list[str]] = {}
    for index, line in enumerate(lines[:-2]):
        if not DEVANAGARI_RE.search(line) or not LATIN_RE.search(line):
            continue
        latin_part = re.sub(r"[\u0900-\u097F।॥|]+", " ", line)
        key = roman_match_key(latin_part)
        if not key:
            continue
        for candidate in lines[index + 1 : index + 5]:
            if DEVANAGARI_RE.search(candidate) and len(DEVANAGARI_RE.findall(candidate)) >= 8 and not LATIN_RE.search(candidate):
                derivations.setdefault(key, [])
                if candidate not in derivations[key]:
                    derivations[key].append(candidate)
                break
    return derivations


def nonblank_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def has_sanskrit_derivation(lines: list[str]) -> bool:
    if len(lines) < 3:
        return False
    for line in lines[1:5]:
        if DEVANAGARI_RE.search(line) and len(DEVANAGARI_RE.findall(line)) >= 8:
            return True
    return False


def suspicious_devanagari_fragments(lines: list[str]) -> list[str]:
    fragments: list[str] = []
    for line in lines[1:6]:
        if not DEVANAGARI_RE.search(line):
            continue
        if LATIN_RE.search(line):
            continue
        devanagari_count = len(DEVANAGARI_RE.findall(line))
        if devanagari_count <= 4:
            fragments.append(line)
    return fragments


def audit_entry(number: int, devanagari: str, roman: str, source_derivations: dict[str, list[str]]) -> EntryAudit:
    text, page = visible_entry_for_number(number)
    issues: list[str] = []
    lines = nonblank_lines(text)
    if not text:
        issues.append("No rendered entry text.")
    if lines and devanagari not in lines[0]:
        issues.append(f"Heading does not contain canonical Devanagari `{devanagari}`.")
    if lines and roman and roman_match_key(roman) in roman_match_key(lines[0]):
        issues.append(f"Heading still exposes IAST `{roman}`.")
    has_derivation = has_sanskrit_derivation(lines)
    source_derivation = source_derivations.get(roman_match_key(roman), [])
    if not has_derivation:
        issues.append("No clear Sanskrit derivation line near the top of the entry.")
        if source_derivation:
            issues.append(f"OCR Studio source has derivation candidate: `{source_derivation[0]}`.")
    for fragment in suspicious_devanagari_fragments(lines):
        issues.append(f"Suspicious Devanagari fragment near heading: `{fragment}`.")
    for pattern, reason in SUSPICIOUS_PATTERNS.items():
        if re.search(pattern, text):
            issues.append(f"Suspicious pattern `{pattern}`: {reason}.")
    for match in BROKEN_SPACING_RE.finditer(text):
        snippet = text[max(0, match.start() - 30) : min(len(text), match.end() + 30)].replace("\n", " ")
        if any(ch in snippet for ch in "āīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ"):
            issues.append(f"Possible broken roman/Sanskrit word spacing near: `{snippet}`.")
            break
    return EntryAudit(number, devanagari, roman, page, text, list(dict.fromkeys(issues)))


def main() -> int:
    source_derivations = load_source_derivations()
    audits: list[EntryAudit] = []
    for row in load_canonical_namas():
        audits.append(audit_entry(int(row["number"]), row["devanagari"], row["roman"], source_derivations))

    flagged = [audit for audit in audits if audit.issues]
    lines: list[str] = [
        "# Rendered Mac Entry Quality Audit",
        "",
        f"Entries checked: {len(audits)}",
        f"Entries flagged: {len(flagged)}",
        f"OCR Studio derivation keys loaded: {len(source_derivations)}",
        "",
        "This audit checks the rendered text that the Mac app displays, not only whether a name is searchable.",
        "",
        "## Flagged Entries",
        "",
        "| No. | Page | Nama | Issue Count |",
        "|---:|---:|---|---:|",
    ]
    for audit in flagged:
        page = "" if audit.page is None else str(audit.page)
        lines.append(f"| {audit.number} | {page} | {audit.devanagari} {audit.roman} | {len(audit.issues)} |")
    lines.append("")
    for audit in flagged:
        lines.append(f"## {audit.number}. {audit.devanagari} {audit.roman}")
        lines.append("")
        if audit.page is not None:
            lines.append(f"Source page: {audit.page}")
            lines.append("")
        for issue in audit.issues:
            lines.append(f"- {issue}")
        lines.append("")
        preview = "\n".join(audit.text.splitlines()[:18]).strip()
        lines.append("```text")
        lines.append(preview)
        lines.append("```")
        lines.append("")

    full_lines: list[str] = ["# Rendered Mac Entries", ""]
    for audit in audits:
        full_lines.append(f"## {audit.number}. {audit.devanagari} {audit.roman}")
        full_lines.append("")
        if audit.issues:
            full_lines.append("Issues:")
            full_lines.extend(f"- {issue}" for issue in audit.issues)
            full_lines.append("")
        full_lines.append("```text")
        full_lines.append(audit.text.strip())
        full_lines.append("```")
        full_lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    FULL_OUT.write_text("\n".join(full_lines), encoding="utf-8")
    print(OUT)
    print(FULL_OUT)
    print(f"entries={len(audits)} flagged={len(flagged)}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
