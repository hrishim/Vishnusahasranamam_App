from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .io import INDEX_DIR
from .textutil import normalize_text


CANONICAL_NAMAS_JSON = INDEX_DIR / "canonical_namas.json"


VOWELS = {
    "अ": "a",
    "आ": "ā",
    "इ": "i",
    "ई": "ī",
    "उ": "u",
    "ऊ": "ū",
    "ऋ": "ṛ",
    "ॠ": "ṝ",
    "ऌ": "ḷ",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
}

VOWEL_SIGNS = {
    "ा": "ā",
    "ि": "i",
    "ी": "ī",
    "ु": "u",
    "ू": "ū",
    "ृ": "ṛ",
    "ॄ": "ṝ",
    "ॢ": "ḷ",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
}

CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "ṅ",
    "च": "c",
    "छ": "ch",
    "ज": "j",
    "झ": "jh",
    "ञ": "ñ",
    "ट": "ṭ",
    "ठ": "ṭh",
    "ड": "ḍ",
    "ढ": "ḍh",
    "ण": "ṇ",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "v",
    "श": "ś",
    "ष": "ṣ",
    "स": "s",
    "ह": "h",
    "ळ": "ḷ",
}

MARKS = {
    "ं": "ṃ",
    "ँ": "m̐",
    "ः": "ḥ",
    "ऽ": "'",
}


def devanagari_key(text: str) -> str:
    text = normalize_text(text).replace(":", "ः")
    return re.sub(r"[^\u0900-\u097F]", "", text)


def devanagari_to_iast(text: str) -> str:
    text = normalize_text(text).replace(":", "ः")
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in VOWELS:
            out.append(VOWELS[ch])
        elif ch in CONSONANTS:
            base = CONSONANTS[ch]
            next_ch = text[i + 1] if i + 1 < len(text) else ""
            if next_ch == "्":
                out.append(base)
                i += 1
            elif next_ch in VOWEL_SIGNS:
                out.append(base + VOWEL_SIGNS[next_ch])
                i += 1
            else:
                out.append(base + "a")
        elif ch in VOWEL_SIGNS:
            out.append(VOWEL_SIGNS[ch])
        elif ch in MARKS:
            out.append(MARKS[ch])
        elif ch in " \t\r\n-":
            out.append(" ")
        elif ch in "()\u200c\u200d":
            pass
        else:
            out.append(ch)
        i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


@lru_cache(maxsize=1)
def load_canonical_namas(path: str = str(CANONICAL_NAMAS_JSON)) -> tuple[dict, ...]:
    source = Path(path)
    if not source.exists():
        return ()
    payload = json.loads(source.read_text(encoding="utf-8"))
    return tuple(payload.get("namas", []))


def canonical_by_number(number: int) -> dict | None:
    for row in load_canonical_namas():
        if int(row.get("number", 0)) == number:
            return row
    return None
