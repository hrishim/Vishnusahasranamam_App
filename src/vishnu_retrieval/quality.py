from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")
ROMAN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9@#$%^*_+=~`'’.-]*")
DEVANAGARI_WORD_RE = re.compile(r"[\u0900-\u097F][\u0900-\u097F\u200c\u200d\u00b7|/\\\\:;,.!?'’`~@#$%^&*+=_-]*")

OCR_SYMBOL_RE = re.compile(r"[@#$%^*_+=~`]")
BROKEN_DEVANAGARI_RE = re.compile(r"(?:^|\s)[\u093e-\u094d\u0951-\u0957](?:\s|$)")
HEADER_WHITELIST = {"VISNUSAHASRANAMA", "VISNU", "VISHNU"}
ROMAN_WHITELIST = {"etc", "mu", "ka", "sve"}

COMMON_SANSKRIT_ROMAN = {
    "atma",
    "bhagavan",
    "bhagavad",
    "brahma",
    "buddhi",
    "dharma",
    "gita",
    "garbhagrha",
    "isvara",
    "jiva",
    "jnana",
    "karma",
    "moksa",
    "nama",
    "namah",
    "parayana",
    "prakasa",
    "prakasatma",
    "punya",
    "sahasranama",
    "sastra",
    "stuti",
    "svarupa",
    "antarjyoti",
    "upanisad",
    "upanisads",
    "visnu",
}


@dataclass
class QualityIssue:
    kind: str
    token: str
    message: str
    line: int


@lru_cache(maxsize=1)
def english_words() -> set[str]:
    path = Path("/usr/share/dict/words")
    if not path.exists():
        return set()
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        word = line.strip().casefold()
        if len(word) >= 3 and word.isalpha():
            words.add(word)
    return words


def looks_like_sanskrit_roman(word: str) -> bool:
    clean = re.sub(r"[^A-Za-z]", "", word).casefold()
    if clean in COMMON_SANSKRIT_ROMAN:
        return True
    endings = ("ah", "am", "ena", "aya", "asya", "atman", "atma", "anam", "ani")
    clusters = ("jn", "ks", "sr", "sv", "bh", "dh", "gh", "kh", "ph", "th", "ch")
    return any(clean.endswith(end) for end in endings) and any(cluster in clean for cluster in clusters)


def english_known(word: str, dictionary: set[str]) -> bool:
    if not dictionary:
        return True
    clean = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", word).casefold()
    if not clean:
        return True
    if clean in dictionary:
        return True
    if "-" in clean or "’" in clean or "'" in clean:
        parts = [part for part in re.split(r"[-'’]+", clean) if part]
        if parts and all(english_known(part, dictionary) for part in parts):
            return True
    candidates = {clean}
    if clean.endswith("ies") and len(clean) >= 4:
        candidates.add(clean[:-3] + "y")
    if clean.endswith("es") and len(clean) >= 4:
        candidates.add(clean[:-2])
    if clean.endswith("s") and len(clean) >= 4:
        candidates.add(clean[:-1])
    if clean.endswith("ed") and len(clean) > 5:
        candidates.add(clean[:-2])
        candidates.add(clean[:-1])
    if clean.endswith("ing") and len(clean) > 6:
        candidates.add(clean[:-3])
        candidates.add(clean[:-3] + "e")
    return any(candidate in dictionary for candidate in candidates)


def audit_text(text: str, max_issues: int = 40) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    dictionary = english_words()

    for line_no, line in enumerate(text.splitlines(), start=1):
        line_has_devanagari = bool(DEVANAGARI_RE.search(line))

        if BROKEN_DEVANAGARI_RE.search(line):
            issues.append(
                QualityIssue(
                    "sanskrit",
                    "",
                    "Possible broken Devanagari sign at a word boundary.",
                    line_no,
                )
            )

        for match in DEVANAGARI_WORD_RE.finditer(line):
            token = match.group(0)
            if LATIN_RE.search(token) or OCR_SYMBOL_RE.search(token):
                issues.append(
                    QualityIssue(
                        "sanskrit",
                        token,
                        "Devanagari token contains Latin letters or OCR artifact symbols.",
                        line_no,
                    )
                )
            if any(ch in token for ch in "|\\/"):
                issues.append(
                    QualityIssue(
                        "sanskrit",
                        token,
                        "Devanagari token contains punctuation that may be an OCR substitution for danda or spacing.",
                        line_no,
                    )
                )

        for match in ROMAN_TOKEN_RE.finditer(line):
            token = match.group(0)
            clean = token.strip("'’").casefold()
            clean_alpha = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", clean)
            if len(clean) < 4:
                continue
            if token in HEADER_WHITELIST or clean_alpha in ROMAN_WHITELIST:
                continue
            if OCR_SYMBOL_RE.search(token) or any(ch.isdigit() for ch in token):
                issues.append(
                    QualityIssue(
                        "english",
                        token,
                        "English/Roman token contains likely OCR artifact characters.",
                        line_no,
                    )
                )
                continue
            if "." in token and any(part[:1].isupper() for part in token.split(".") if part):
                continue
            if token.isupper() and token not in HEADER_WHITELIST and not english_known(token, dictionary):
                issues.append(
                    QualityIssue(
                        "english",
                        token,
                        "All-caps token is not recognized; it may be an OCR-corrupted headword.",
                        line_no,
                    )
                )
                continue
            if looks_like_sanskrit_roman(token):
                continue
            if dictionary and not english_known(clean_alpha, dictionary):
                issues.append(
                    QualityIssue(
                        "english",
                        token,
                        "Word is not in the local English dictionary; check OCR spelling.",
                        line_no,
                    )
                )

        if len(issues) >= max_issues:
            return issues[:max_issues]
    return issues


def format_quality_issues(issues: list[QualityIssue]) -> str:
    if not issues:
        return "Spell/OCR audit: no obvious English or Devanagari OCR issues detected."
    lines = ["Spell/OCR audit:"]
    for issue in issues:
        token = f" `{issue.token}`" if issue.token else ""
        lines.append(f"- line {issue.line} [{issue.kind}]{token}: {issue.message}")
    return "\n".join(lines)
