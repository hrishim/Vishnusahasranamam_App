from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter

TOKEN_RE = re.compile(r"[\w\u0900-\u097F]+", re.UNICODE)


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def tokenize(text: str) -> list[str]:
    return [tok.casefold() for tok in TOKEN_RE.findall(normalize_text(text))]


def sparse_vector(text: str, dims: int = 2048) -> dict[str, float]:
    """Build a deterministic local vector from word and character n-grams."""
    text = normalize_text(text).casefold()
    grams: list[str] = []
    tokens = tokenize(text)
    grams.extend(f"w:{tok}" for tok in tokens)
    compact = re.sub(r"\s+", " ", text).strip()
    for n in (3, 4, 5):
        if len(compact) >= n:
            grams.extend(f"c{n}:{compact[i:i+n]}" for i in range(len(compact) - n + 1))
    if not grams:
        return {}
    counts = Counter(grams)
    values: dict[str, float] = {}
    for gram, count in counts.items():
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=4).digest()
        bucket = str(int.from_bytes(digest, "big") % dims)
        values[bucket] = values.get(bucket, 0.0) + float(count)
    norm = math.sqrt(sum(value * value for value in values.values())) or 1.0
    return {key: value / norm for key, value in values.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(key, 0.0) for key, value in a.items())


def paragraph_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalize_text(text)) if block.strip()]
    return blocks or [normalize_text(text).strip()]

