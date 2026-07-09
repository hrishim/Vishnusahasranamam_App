from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from docx import Document


SOURCE = Path("/Users/sathyavasu/Projects/codex/PDF_OCR_Studio/output/The-Teaching-of-Visnusahasranama-clean.docx")
OUT_DIR = Path("outputs/clean_doc_check")
REPORT = OUT_DIR / "clean_docx_audit.md"
TEXT_OUT = OUT_DIR / "clean_docx_text.txt"

EXPECTED_NAMES = [
    "Viśvam",
    "Viṣṇuḥ",
    "Vaṣaṭkāraḥ",
    "Bhūtabhavyabhavatprabhuḥ",
    "Bhūtakṛt",
    "Bhūtabhṛt",
    "Bhāvaḥ",
    "Bhūtātmā",
    "Bhūtabhāvanaḥ",
    "Pūtātmā",
    "Paramātmā",
    "Muktānām",
    "Aprameyaḥ",
    "Hṛṣīkeśaḥ",
    "Padmanābhaḥ",
    "Anuttamaḥ",
    "Mahābhāgaḥ",
    "Hetuḥ",
    "Nārāyaṇaḥ",
    "Vāsudevaḥ",
]

QUERIES = [
    "Aprameya",
    "अप्रमेय",
    "The one who is not an object of knowledge",
    "bhaga",
    "six-fold virtues",
    "three Vedas",
    "pranava",
    "come from pranava",
    "where does the three Vedas come from",
    "Hṛṣīkeśa",
    "वासुदेव",
]

BAD_GLYPHS = re.compile(r"[\uFFFD□■�]")
BROKEN_SPACING = re.compile(
    r"\b(?:studentsliving|self- consciousness|self- knowledge|time- bound|space- wise|object- wise|"
    r"God- cognition|flower- cognition|saguṇa- brahma|dṛṣṭa- phala|adṛṣṭa- phala)\b",
    re.IGNORECASE,
)
MISSING_K_Q_WORDS = re.compile(
    r"\b(?:nowledge|nown|nower|mar et|loc er|loo s|wor s|en uiry|uestion|uni ue|"
    r"ta e|ma e|li e|indly|thin ing|pra ti|pra ṛti| arta| arana| anga| ripa)\b",
    re.IGNORECASE,
)
ODD_SYMBOL_RUN = re.compile(r"[^\w\s\u0900-\u097F.,;:'\"()|/\\\-–—‘’“”!?āīūṛṝḷḹṅñṭḍṇśṣḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢḤ]{3,}")
LONG_TOKEN = re.compile(r"\S{55,}")
LIKELY_HEADER_FRAGMENT = re.compile(r"^\d{1,3}\s*$")


def paragraphs() -> list[str]:
    doc = Document(str(SOURCE))
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def snippet(text: str, needle: str, width: int = 360) -> str | None:
    low = text.lower()
    idx = low.find(needle.lower())
    if idx < 0:
        return None
    start = max(0, idx - width // 2)
    end = min(len(text), idx + len(needle) + width // 2)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paras = paragraphs()
    text = "\n\n".join(paras)
    TEXT_OUT.write_text(text, encoding="utf-8")

    issues: list[tuple[int, str, str]] = []
    for i, para in enumerate(paras, 1):
        reasons = []
        if BAD_GLYPHS.search(para):
            reasons.append("bad replacement glyph")
        if BROKEN_SPACING.search(para):
            reasons.append("known broken spacing")
        if MISSING_K_Q_WORDS.search(para):
            reasons.append("likely missing k/q or split word")
        if ODD_SYMBOL_RUN.search(para):
            reasons.append("odd symbol run")
        if LONG_TOKEN.search(para):
            reasons.append("very long token")
        if reasons:
            issues.append((i, ", ".join(sorted(set(reasons))), para[:500]))

    token_counts = Counter(re.findall(r"[A-Za-zāīūṛṝḷḹṅñṭḍṇśṣḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢḤ]+", text))
    suspicious_tokens = [
        (tok, count)
        for tok, count in token_counts.most_common()
        if len(tok) > 2 and MISSING_K_Q_WORDS.fullmatch(tok)
    ]

    lines: list[str] = []
    lines.append("# Clean DOCX Source Audit")
    lines.append("")
    lines.append(f"Source: `{SOURCE}`")
    lines.append(f"Paragraphs: {len(paras):,}")
    lines.append(f"Characters: {len(text):,}")
    lines.append(f"Devanagari characters: {sum(1 for c in text if '\u0900' <= c <= '\u097F'):,}")
    lines.append(f"Roman diacritic characters: {sum(1 for c in text if c in 'āīūṛṝḷḹṅñṭḍṇśṣḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢḤ'):,}")
    lines.append("")
    lines.append("## Searchability Checks")
    lines.append("")
    for query in QUERIES:
        count = len(re.findall(re.escape(query), text, flags=re.IGNORECASE))
        sample = snippet(text, query)
        lines.append(f"- `{query}`: {count} hit(s)")
        if sample:
            lines.append(f"  - Sample: {sample}")
    lines.append("")
    lines.append("## Expected Name Checks")
    lines.append("")
    for name in EXPECTED_NAMES:
        count = len(re.findall(re.escape(name), text, flags=re.IGNORECASE))
        lines.append(f"- `{name}`: {count} hit(s)")
    lines.append("")
    lines.append("## Suspicious Paragraphs")
    lines.append("")
    lines.append(f"Flagged paragraphs: {len(issues):,}")
    lines.append("")
    for i, reason, para in issues[:150]:
        safe = para.replace("|", "\\|")
        lines.append(f"- Paragraph {i}: {reason}: {safe}")
    if len(issues) > 150:
        lines.append(f"- ... {len(issues) - 150:,} more flagged paragraphs")
    lines.append("")
    lines.append("## Suspicious Token Counts")
    lines.append("")
    if suspicious_tokens:
        for token, count in suspicious_tokens[:80]:
            lines.append(f"- `{token}`: {count}")
    else:
        lines.append("No suspicious token count matches.")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)
    print(TEXT_OUT)
    print(f"flagged_paragraphs={len(issues)}")


if __name__ == "__main__":
    main()
