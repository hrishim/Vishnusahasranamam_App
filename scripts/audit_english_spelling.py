from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from spellchecker import SpellChecker

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.desktop_app import entry_body_with_clean_heading
from vishnu_retrieval.search import extract_entry_by_number


OUT = Path("outputs/clean_doc_check/english_spelling_audit.md")
FULL_RENDERED = Path("outputs/clean_doc_check/rendered_entries_quality_full.md")

WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’]{2,}\b")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


DOMAIN_ALLOW = {
    "abhava",
    "abhidhana",
    "abhidheya",
    "adharma",
    "adhisthana",
    "agni",
    "ananda",
    "ananta",
    "ananya",
    "anta",
    "antah",
    "antahkarana",
    "anupalabdhi",
    "anumama",
    "anumana",
    "apaurusheya",
    "artha",
    "arthapatti",
    "asura",
    "asuras",
    "atma",
    "bhagavad",
    "bhagavan",
    "bhagavat",
    "bhakti",
    "brahma",
    "brahman",
    "brahmana",
    "brahmanas",
    "cit",
    "citta",
    "cognitions",
    "buddhi",
    "deva",
    "devas",
    "devata",
    "devatas",
    "dharma",
    "dharmas",
    "gita",
    "gita",
    "guna",
    "gunas",
    "guru",
    "hetu",
    "hiranyagarbha",
    "isvara",
    "isness",
    "jagat",
    "janma",
    "jiva",
    "jivas",
    "jnana",
    "kama",
    "karma",
    "karmas",
    "karta",
    "kartr",
    "kosa",
    "kosas",
    "krishna",
    "lakshmi",
    "loka",
    "lokas",
    "maya",
    "moksa",
    "moksha",
    "nama",
    "namas",
    "narayana",
    "nirguna",
    "omkara",
    "papa",
    "paramatma",
    "paratman",
    "pralaya",
    "pramana",
    "prameya",
    "pramata",
    "prana",
    "pranas",
    "prarabdha",
    "pratyaksa",
    "punya",
    "purana",
    "puranas",
    "purusa",
    "purushartha",
    "raga",
    "rajas",
    "rishi",
    "rishis",
    "sadhaka",
    "sadhana",
    "sadhya",
    "saguna",
    "sahasranama",
    "sakshi",
    "samsara",
    "samsari",
    "sankalpa",
    "sankara",
    "sanskrit",
    "sastra",
    "satya",
    "satyam",
    "shastra",
    "shraddha",
    "sloka",
    "smrti",
    "sraddha",
    "sri",
    "sruti",
    "sukha",
    "tamas",
    "upamana",
    "upanisad",
    "upanisads",
    "upanishad",
    "upanishads",
    "upasana",
    "vairagya",
    "vasana",
    "veda",
    "vedas",
    "vedanta",
    "vedantin",
    "vishnu",
    "visnu",
    "yajna",
    "yoga",
    "yogi",
}


COMMON_ALLOW = {
    "app",
    "apps",
    "bmsc",
    "ceo",
    "codex",
    "colour",
    "colours",
    "elementals",
    "etc",
    "docx",
    "favourable",
    "favourite",
    "favourites",
    "github",
    "indweller",
    "indwellers",
    "mac",
    "ocr",
    "pdf",
    "pwa",
    "potness",
    "renderer",
    "rendered",
    "recognise",
    "recognised",
    "recognises",
    "recognising",
    "realise",
    "realised",
    "realises",
    "realising",
    "swamiji",
    "unmanifest",
    "url",
    "urls",
    "valour",
}


SANSKRITISH_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"(?:bh|dh|gh|jh|kh|ph|th|sh|jn|ny|ks|tm|sv|pr|tr|dv|vr)",
        r"(?:aya|ena|asya|atva|tva|rupa|svarupa|karaka|bhava|maya|loka|guna|dharma|karma)$",
        r"(?:opanisad|upanisad|purana|sutra|smrti|sruti)$",
    ]
]


@dataclass(frozen=True)
class SpellHit:
    word: str
    count: int
    suggestion: str
    entries: list[int]
    context: str


def strip_diacritics(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def rendered_entries() -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    full_lines = ["# Rendered Mac Entries For English Spell Audit", ""]
    for row in load_canonical_namas():
        number = int(row["number"])
        hits = extract_entry_by_number(number, window_after=5)
        if not hits:
            continue
        text = entry_body_with_clean_heading(hits[0])
        entries.append((number, text))
        full_lines.append(f"## {number}. {row['devanagari']} {row['roman']}")
        full_lines.append("")
        full_lines.append("```text")
        full_lines.append(text.strip())
        full_lines.append("```")
        full_lines.append("")
    FULL_RENDERED.parent.mkdir(parents=True, exist_ok=True)
    FULL_RENDERED.write_text("\n".join(full_lines), encoding="utf-8")
    return entries


def domain_allowlist() -> set[str]:
    allowed = set(DOMAIN_ALLOW) | set(COMMON_ALLOW)
    for row in load_canonical_namas():
        for field in ("roman", "ascii"):
            value = strip_diacritics(str(row.get(field, "")))
            for part in re.findall(r"[a-z]{3,}", value):
                allowed.add(part)
    return allowed


def likely_sanskrit_word(word: str) -> bool:
    lower = word.lower()
    if lower in DOMAIN_ALLOW:
        return True
    if len(lower) <= 4 and lower not in {"teh", "nad", "fo", "fro", "tha"}:
        return True
    if lower.endswith(("ah", "am", "at", "ena", "aya", "asya", "ani", "tva", "tvam", "vat", "van", "man")):
        return True
    if any(part in lower for part in ("bh", "dh", "jn", "ks", "sh", "sv", "atman", "isvara", "ishvara")):
        return True
    return any(pattern.search(lower) for pattern in SANSKRITISH_PATTERNS)


def context_for(text: str, word: str) -> str:
    match = re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - 90)
    end = min(len(text), match.end() + 140)
    return text[start:end].replace("\n", " ").replace("|", "/")


def main() -> int:
    spell = SpellChecker(language="en", distance=1)
    allowed = domain_allowlist()
    counts: Counter[str] = Counter()
    entries_by_word: dict[str, set[int]] = defaultdict(set)
    contexts: dict[str, str] = {}

    for number, text in rendered_entries():
        # Remove Devanagari lines before extracting English-like words.
        englishish_lines = [line for line in text.splitlines() if not DEVANAGARI_RE.search(line)]
        englishish = "\n".join(englishish_lines)
        for token in WORD_RE.findall(englishish):
            word = token.strip("'’").replace("’", "'")
            lower = word.lower()
            if lower in allowed:
                continue
            if likely_sanskrit_word(lower):
                continue
            if spell.known([lower]):
                continue
            # OCR often leaves Sanskrit titles in ASCII; keep the report focused by
            # ignoring long low-vowel transliteration-like tokens.
            vowel_count = sum(1 for ch in lower if ch in "aeiou")
            if len(lower) >= 9 and vowel_count <= 2:
                continue
            counts[lower] += 1
            entries_by_word[lower].add(number)
            contexts.setdefault(lower, context_for(englishish, word))

    hits: list[SpellHit] = []
    sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    report_words = {word for word, _count in sorted_counts[:500]}
    for word, count in sorted_counts:
        suggestion = ""
        if word in report_words and len(word) <= 18:
            suggestion = spell.correction(word) or ""
        hits.append(
            SpellHit(
                word=word,
                count=count,
                suggestion=suggestion if suggestion != word else "",
                entries=sorted(entries_by_word[word])[:12],
                context=contexts.get(word, ""),
            )
        )
    hits.sort(key=lambda item: (-item.count, item.word))

    lines = [
        "# English Spelling Audit",
        "",
        f"Rendered entries checked: {len(rendered_entries())}",
        f"Candidate misspelled English words: {len(hits)}",
        "",
        "This report intentionally filters common Sanskrit/IAST vocabulary, so remaining rows need human review before correction.",
        "",
        "| Count | Word | Suggested | Entries | Context |",
        "|---:|---|---|---|---|",
    ]
    for hit in hits[:500]:
        entries = ", ".join(str(number) for number in hit.entries)
        lines.append(f"| {hit.count} | `{hit.word}` | `{hit.suggestion}` | {entries} | {hit.context} |")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(f"candidates={len(hits)}")
    for hit in hits[:80]:
        print(f"{hit.count:4} {hit.word:24} -> {hit.suggestion} [{', '.join(map(str, hit.entries[:5]))}]")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
