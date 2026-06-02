from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .indexer import keyword_score
from .io import INDEX_JSON, PAGES_JSONL, SLOKAS_JSON, read_index, read_pages
from .textutil import cosine, normalize_text, sparse_vector, tokenize


ROMAN_INITIAL_CHARS = "A-ZĀĪŪṚṜḶṄÑṬḌṆŚṢḤ"
ROMAN_CHARS = "A-Za-zāīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ"

ENTRY_HEADING_RE = re.compile(
    rf"(?m)^\s*(?:(?:\d{{1,4}}|(?:\d{{1,4}}\s+and\s+\d{{1,4}}))[.;][^\S\n]+)?[\u0900-\u097F][^\n]{{0,90}}?[^\S\n]+[{ROMAN_INITIAL_CHARS}][{ROMAN_CHARS}'’.-]+(?:[^\n]*)?$"
)
NAMA_HEADING_RE = re.compile(
    rf"^\s*(?:(?:\d{{1,4}}|(?:\d{{1,4}}\s+and\s+\d{{1,4}}))[.;][^\S\n]+)?"
    r"(?P<sanskrit>[\u0900-\u097F][\u0900-\u097F\s:;ऽ\-]+?)"
    r"[^\S\n]+"
    rf"(?P<roman>[{ROMAN_INITIAL_CHARS}][{ROMAN_CHARS}'’.-]+)"
    r"(?P<rest>[^\n]*)$"
)
SCRIPTURE_ROMAN_RE = re.compile(
    r"^(?:BG|MB|Mu\.?Up|Tai\.?Up|Ta\.?Up|Ka\.?Up|Vi\.?Pu|Vi|Harivamsa|Yogasiitra|YE|Arth)\.?:?$"
)
VERSE_NUMBER_RE = re.compile(r"[।|]{2}.*(?:\d|[०-९])")
VERSE_END_RE = re.compile(r"(?:[।|]\s*){2,}.*(?:\d|[०-९])")
LATIN_TRANSLIT_RE = re.compile(r"[A-Za-zāīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ]")
SLOKA_PAGE_OVERRIDES = {
    13: 44,
    33: 94,
    57: 145,
    80: 187,
    87: 199,
    88: 202,
    105: 234,
}


@dataclass
class SearchHit:
    score: float
    page_start: int
    page_end: int
    chunk_id: str
    text: str
    keyword_score: float
    vector_score: float
    warnings: list[str]


@dataclass
class EntryHit:
    page_start: int
    page_end: int
    text: str
    warnings: list[str]


@dataclass
class SlokaHit:
    page: int
    text: str
    warnings: list[str]


@dataclass
class SlokaRecord:
    number: int
    devanagari: str
    roman: str
    text: str
    source_url: str = ""


@dataclass
class SlokaEvent:
    number: int
    page: int
    start: int
    end: int
    warnings: list[str]


def latin_fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", normalize_text(text)).casefold()
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def roman_match_key(text: str) -> str:
    folded = latin_fold(text)
    folded = folded.replace("sh", "s")
    folded = re.sub(r"[^a-z]", "", folded)
    return folded[:-1] if folded.endswith("h") else folded


def devanagari_match_key(text: str) -> str:
    text = normalize_text(text).replace(":", "ः")
    return re.sub(r"[^\u0900-\u097F]", "", text)


def expand_devanagari_key(key: str) -> set[str]:
    key = key.strip("।॥")
    if not key:
        return set()
    forms = {key, key.replace("्", "")}
    for item in list(forms):
        if item.endswith("ः"):
            stem = item[:-1]
            forms.update({stem, stem + "ो"})
        if item.endswith("ो"):
            stem = item[:-1]
            forms.add(stem)
    for item in list(forms):
        if item.startswith("अ") and len(item) > 2:
            stem = item[1:]
            forms.update({stem, stem + "ो", stem + "ः"})
    return {item for item in forms if item}


def devanagari_word_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for token in re.findall(r"[\u0900-\u097F]+", text):
        pieces = [token]
        if "ऽ" in token:
            pieces.extend(part for part in token.split("ऽ") if part)
        for piece in pieces:
            key = devanagari_match_key(piece).strip("।॥")
            keys.update(expand_devanagari_key(key))
    return keys


def devanagari_variants_in_text(variants: set[str], text: str) -> bool:
    word_keys = devanagari_word_keys(text)
    if variants.intersection(word_keys):
        return True
    for variant in variants:
        if len(variant) < 4:
            continue
        if any(variant in word_key for word_key in word_keys):
            return True
    return False


def devanagari_keys_match(query: str, heading: str) -> bool:
    query_key = devanagari_match_key(query)
    heading_key = devanagari_match_key(heading)
    if not query_key or not heading_key:
        return False
    if query_key == heading_key:
        return True
    if query_key.rstrip("ः") == heading_key.rstrip("ः"):
        return True
    if len(query_key) >= 6 and query_key.replace("र्", "").rstrip("ः") == heading_key.replace("र्", "").rstrip("ः"):
        return True
    return query_key.replace("्", "").rstrip("ः") == heading_key.replace("्", "").rstrip("ः")


def parse_nama_heading(line: str) -> tuple[str, str] | None:
    match = NAMA_HEADING_RE.match(line.strip())
    if not match:
        return None
    roman = match.group("roman").strip()
    rest = match.group("rest").strip()
    if any(mark in rest for mark in "।॥|"):
        return None
    if "." in roman or SCRIPTURE_ROMAN_RE.match(roman):
        return None
    sanskrit = match.group("sanskrit").strip()
    if any(mark in sanskrit for mark in "।॥|"):
        return None
    return sanskrit, roman


def heading_matches_query(entry_text: str, query: str) -> bool:
    heading = entry_text.splitlines()[0].strip() if entry_text.splitlines() else ""
    parsed = parse_nama_heading(heading)
    if not parsed:
        return False
    sanskrit, roman = parsed
    if devanagari_match_key(query):
        return devanagari_keys_match(query, sanskrit)
    needle = normalize_text(query).casefold()
    if needle and needle in normalize_text(sanskrit).casefold():
        return True
    folded_needle = roman_match_key(query)
    folded_haystack = roman_match_key(roman)
    if not folded_needle:
        return False
    if len(folded_needle) <= 3:
        return folded_needle == folded_haystack
    return folded_needle in folded_haystack


def heading_occurrences(page_text: str, query: str) -> list[int]:
    occurrences: list[int] = []
    offset = 0
    for line in page_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and heading_matches_query(stripped, query):
            occurrences.append(offset + line.find(stripped))
        offset += len(line)
    return occurrences


def trim_trailing_verse_prelude(text: str) -> str:
    lines = text.rstrip().splitlines()
    verse_line = None
    for index in range(len(lines) - 1, max(-1, len(lines) - 12), -1):
        if "।।" in lines[index]:
            verse_line = index
            break
    if verse_line is None:
        return text.strip()

    start = verse_line
    while start > 0:
        previous = lines[start - 1].strip()
        if not previous or not any("\u0900" <= ch <= "\u097F" for ch in previous):
            break
        start -= 1

    block = "\n".join(lines[start:]).strip()
    if "||" in block and "।।" in block:
        return "\n".join(lines[:start]).strip()
    return text.strip()


def has_devanagari_text(line: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" and ch not in "।॥" for ch in line)


def has_latin_translit(line: str) -> bool:
    return bool(LATIN_TRANSLIT_RE.search(line))


def has_verse_end(line: str) -> bool:
    return bool(VERSE_END_RE.search(line))


def has_roman_verse_end(line: str) -> bool:
    return has_verse_end(line) or bool(re.search(r"[|।].*(?:\d|[०-९])", line))


def line_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        spans.append((line, offset, offset + len(line)))
        offset += len(raw_line)
    if text and not spans:
        spans.append((text, 0, len(text)))
    return spans


def is_devanagari_verse_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if parse_nama_heading(stripped):
        return False
    return has_devanagari_text(stripped)


def is_roman_verse_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if parse_nama_heading(stripped):
        return False
    if "." in stripped:
        return False
    return has_latin_translit(stripped) and ("|" in stripped or "।" in stripped or has_verse_end(stripped))


def sloka_blocks(text: str) -> list[tuple[int, int, str]]:
    spans = line_spans(text)
    blocks: list[tuple[int, int, str]] = []
    i = 0
    while i < len(spans):
        line, start, _ = spans[i]
        if not is_devanagari_verse_line(line):
            i += 1
            continue

        j = i
        has_end = False
        blank_bridge = False
        while j < len(spans):
            if is_devanagari_verse_line(spans[j][0]):
                has_end = has_end or has_verse_end(spans[j][0])
                blank_bridge = False
                j += 1
                continue
            if (
                not has_end
                and not blank_bridge
                and not spans[j][0].strip()
                and j + 1 < len(spans)
                and is_devanagari_verse_line(spans[j + 1][0])
            ):
                blank_bridge = True
                j += 1
                continue
            break
        if not has_end:
            i += 1
            continue

        block_end = spans[j - 1][2]
        probe = j
        blanks_before_roman: list[int] = []
        while probe < len(spans) and not spans[probe][0].strip() and len(blanks_before_roman) < 2:
            blanks_before_roman.append(probe)
            probe += 1

        if probe < len(spans) and is_roman_verse_line(spans[probe][0]):
            roman = probe
            roman_has_end = False
            blank_run = 0
            last_content = probe
            while roman < len(spans):
                roman_line = spans[roman][0]
                if not roman_line.strip():
                    if roman_has_end or blank_run >= 1:
                        break
                    blank_run += 1
                    roman += 1
                    continue
                if not is_roman_verse_line(roman_line):
                    break
                roman_has_end = roman_has_end or has_roman_verse_end(roman_line)
                blank_run = 0
                last_content = roman
                roman += 1
                if roman_has_end:
                    break
            if roman_has_end:
                block_end = spans[last_content][2]
                j = roman

        blocks.append((start, block_end, text[start:block_end].strip()))
        i = max(j, i + 1)
    return blocks


def containing_sloka(text: str, occurrence: int) -> str | None:
    for start, end, block in sloka_blocks(text):
        if start <= occurrence < end:
            return block
    return None


def sloka_matches_headword(block: str, sanskrit: str, roman: str = "") -> bool:
    query_key = devanagari_match_key(sanskrit)
    if query_key:
        variants = expand_devanagari_key(query_key)
        if devanagari_variants_in_text(variants, block):
            return True

    roman_key = roman_match_key(roman)
    if not roman_key or len(roman_key) <= 3:
        return False
    block_key = roman_match_key(block)
    roman_variants = {roman_key}
    if roman_key.startswith("a") and len(roman_key) > 4:
        roman_variants.add(roman_key[1:])
    return any(variant in block_key for variant in roman_variants)


DEVANAGARI_DIGIT_TRANS = str.maketrans("०१२३४५६७८९", "0123456789")


def parse_int_token(text: str) -> int | None:
    cleaned = re.sub(r"\D", "", text.translate(DEVANAGARI_DIGIT_TRANS))
    if not cleaned:
        return None
    value = int(cleaned)
    return value if 1 <= value <= 108 else None


def query_sloka_number(query: str) -> int | None:
    text = normalize_text(query)
    if not text:
        return None
    compact = re.sub(r"[^\d०-९]", "", text)
    if compact and len(compact) == len(text.replace(" ", "")):
        return parse_int_token(compact)
    return None


def sloka_number_from_block(block: str) -> int | None:
    candidates: list[str] = []
    for match in re.finditer(r"(?:[।|]\s*){2,}\s*([०-९0-9]{1,3})", block):
        candidates.append(match.group(1))
    for match in re.finditer(r"\(\s*([0-9]{1,3})\s*\)", block):
        candidates.append(match.group(1))
    for candidate in reversed(candidates):
        value = parse_int_token(candidate)
        if value is not None:
            return value
    return None


@lru_cache(maxsize=4)
def load_clean_slokas(slokas_path: str = str(SLOKAS_JSON)) -> tuple[SlokaRecord, ...]:
    path = Path(slokas_path)
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: list[SlokaRecord] = []
    for row in payload.get("slokas", []):
        records.append(
            SlokaRecord(
                number=int(row["number"]),
                devanagari=normalize_text(row.get("devanagari", "")),
                roman=normalize_text(row.get("roman", "")),
                text=normalize_text(row.get("text", "")),
                source_url=row.get("source_url", ""),
            )
        )
    return tuple(records)


def clean_sloka_by_number(number: int) -> SlokaRecord | None:
    for record in load_clean_slokas():
        if record.number == number:
            return record
    return None


def clean_sloka_matches_query(record: SlokaRecord, query: str, ignore_case: bool = True) -> bool:
    needle = normalize_text(query)
    if not needle:
        return False
    number = query_sloka_number(needle)
    if number is not None:
        return record.number == number
    haystack = record.text.casefold() if ignore_case else record.text
    needle_cmp = needle.casefold() if ignore_case else needle
    if needle_cmp in haystack:
        return True
    if devanagari_match_key(needle):
        return sloka_matches_headword(record.text, needle)
    roman_needle = roman_match_key(needle)
    return bool(roman_needle and roman_needle in roman_match_key(record.text))


def clean_sloka_for_local_block(block: str) -> SlokaRecord | None:
    number = sloka_number_from_block(block)
    if number is None:
        return None
    record = clean_sloka_by_number(number)
    if not record:
        return None
    block_keys = devanagari_word_keys(block)
    record_keys = devanagari_word_keys(record.devanagari)
    if len(block_keys.intersection(record_keys)) >= 3:
        return record
    block_roman = roman_match_key(block)
    record_roman = roman_match_key(record.roman)
    if record_roman and len(record_roman) > 12 and record_roman[:12] in block_roman:
        return record
    return None


def clean_sloka_position_in_page(page_text: str, record: SlokaRecord) -> int | None:
    positions: list[int] = []
    for token in re.findall(r"[\u0900-\u097F]+", record.devanagari):
        key = devanagari_match_key(token)
        if len(key) < 4:
            continue
        pos = page_text.find(token)
        if pos != -1:
            positions.append(pos)
    page_roman = roman_match_key(page_text)
    for token in re.findall(r"[A-Za-zāīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ']+", record.roman):
        key = roman_match_key(token)
        if len(key) < 6:
            continue
        if key in page_roman:
            positions.append(0)
            break
    if len(positions) < 2:
        return None
    return min(positions)


@lru_cache(maxsize=8)
def sloka_events(pages_jsonl: str = str(PAGES_JSONL)) -> tuple[SlokaEvent, ...]:
    events: list[SlokaEvent] = []
    seen_numbers: set[int] = set()
    for page in read_pages(Path(pages_jsonl)):
        page_text = normalize_text(page.text)
        for start, end, block in sloka_blocks(page_text):
            record = clean_sloka_for_local_block(block)
            if not record:
                continue
            seen_numbers.add(record.number)
            events.append(
                SlokaEvent(
                    number=record.number,
                    page=page.page,
                    start=start,
                    end=end,
                    warnings=page.warnings,
                )
            )
        for number, override_page in SLOKA_PAGE_OVERRIDES.items():
            if number in seen_numbers or page.page != override_page:
                continue
            record = clean_sloka_by_number(number)
            if not record:
                continue
            position = clean_sloka_position_in_page(page_text, record)
            if position is None:
                continue
            seen_numbers.add(number)
            events.append(
                SlokaEvent(
                    number=number,
                    page=page.page,
                    start=position,
                    end=position,
                    warnings=page.warnings,
                )
            )
    return tuple(events)


def sloka_hit_for_number(number: int, pages_jsonl: Path = PAGES_JSONL) -> SlokaHit | None:
    record = clean_sloka_by_number(number)
    if not record:
        return None
    matching_events = [event for event in sloka_events(str(pages_jsonl)) if event.number == number]
    if matching_events:
        event = matching_events[0]
        return SlokaHit(page=event.page, text=record.text, warnings=event.warnings)
    override_page = SLOKA_PAGE_OVERRIDES.get(number, 0)
    return SlokaHit(page=override_page, text=record.text, warnings=[])


@lru_cache(maxsize=8)
def nama_sloka_cross_index(pages_jsonl: str = str(PAGES_JSONL)) -> dict[tuple[int, str], int]:
    pages = read_pages(Path(pages_jsonl))
    events_by_page: dict[int, list[SlokaEvent]] = {}
    for event in sloka_events(pages_jsonl):
        events_by_page.setdefault(event.page, []).append(event)

    cross_index: dict[tuple[int, str], int] = {}
    current_sloka_number: int | None = None
    for page in pages:
        page_text = normalize_text(page.text)
        timeline: list[tuple[int, str, str | SlokaEvent]] = []
        for event in events_by_page.get(page.page, []):
            timeline.append((event.start, "sloka", event))
        for match in ENTRY_HEADING_RE.finditer(page_text):
            heading = match.group(0).strip()
            if parse_nama_heading(heading):
                timeline.append((match.start(), "heading", heading))
        for _, kind, item in sorted(timeline, key=lambda value: (value[0], value[1])):
            if kind == "sloka" and isinstance(item, SlokaEvent):
                current_sloka_number = item.number
            elif kind == "heading" and isinstance(item, str) and current_sloka_number is not None:
                cross_index[(page.page, item)] = current_sloka_number
    return cross_index


def cross_indexed_sloka_for_entry(entry: EntryHit, pages_jsonl: Path = PAGES_JSONL) -> SlokaHit | None:
    heading = entry.text.splitlines()[0].strip() if entry.text.splitlines() else ""
    if not heading:
        return None
    number = nama_sloka_cross_index(str(pages_jsonl)).get((entry.page_start, heading))
    if number is None:
        return None
    return sloka_hit_for_number(number, pages_jsonl)


def load_hits(index_path: Path = INDEX_JSON) -> tuple[list[dict], dict]:
    index = read_index(index_path)
    return index.get("chunks", []), index.get("keyword", {})


def hybrid_search(
    query: str,
    index_path: Path = INDEX_JSON,
    top_k: int = 8,
    keyword_weight: float = 0.55,
    vector_weight: float = 0.45,
) -> list[SearchHit]:
    chunks, stats = load_hits(index_path)
    q_tokens = tokenize(query)
    q_vector = sparse_vector(query)
    raw_hits: list[SearchHit] = []
    keyword_scores: list[float] = []
    vector_scores: list[float] = []

    for chunk in chunks:
        ks = keyword_score(q_tokens, chunk["text"], stats)
        vs = cosine(q_vector, chunk.get("vector", {}))
        keyword_scores.append(ks)
        vector_scores.append(vs)
        raw_hits.append(
            SearchHit(
                score=0.0,
                page_start=chunk["page_start"],
                page_end=chunk["page_end"],
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                keyword_score=ks,
                vector_score=vs,
                warnings=chunk.get("warnings", []),
            )
        )

    max_keyword = max(keyword_scores) if keyword_scores else 0.0
    max_vector = max(vector_scores) if vector_scores else 0.0
    scored: list[SearchHit] = []
    for hit in raw_hits:
        norm_keyword = hit.keyword_score / max_keyword if max_keyword else 0.0
        norm_vector = hit.vector_score / max_vector if max_vector else 0.0
        hit.score = keyword_weight * norm_keyword + vector_weight * norm_vector
        if hit.score > 0:
            scored.append(hit)
    return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]


def exact_search(query: str, pages_jsonl: Path = PAGES_JSONL, ignore_case: bool = False) -> list[dict]:
    pages = read_pages(pages_jsonl)
    needle = normalize_text(query)
    if ignore_case:
        needle_cmp = needle.casefold()
    else:
        needle_cmp = needle
    hits: list[dict] = []
    for page in pages:
        haystack = normalize_text(page.text)
        haystack_cmp = haystack.casefold() if ignore_case else haystack
        start = haystack_cmp.find(needle_cmp)
        while start != -1:
            passage = passage_around(haystack, start, len(needle))
            local_sloka = containing_sloka(haystack, start)
            clean_sloka = clean_sloka_for_local_block(local_sloka) if local_sloka else None
            hits.append(
                {
                    "page": page.page,
                    "passage": passage,
                    "sloka": clean_sloka.text if clean_sloka else local_sloka,
                    "warnings": page.warnings,
                }
            )
            start = haystack_cmp.find(needle_cmp, start + max(1, len(needle_cmp)))
    return hits


def sloka_search(query: str, pages_jsonl: Path = PAGES_JSONL, ignore_case: bool = True) -> list[SlokaHit]:
    needle = normalize_text(query)
    if not needle:
        return []
    number = query_sloka_number(needle)
    if number is not None:
        hit = sloka_hit_for_number(number, pages_jsonl)
        return [hit] if hit else []

    hits: list[SlokaHit] = []
    seen: set[str] = set()

    for record in load_clean_slokas():
        if not clean_sloka_matches_query(record, needle, ignore_case=ignore_case):
            continue
        hit = sloka_hit_for_number(record.number, pages_jsonl)
        if not hit or hit.text in seen:
            continue
        seen.add(hit.text)
        hits.append(hit)

    for entry in extract_entry(query, pages_jsonl):
        hit = preceding_sloka_for_entry(entry, pages_jsonl)
        if not hit:
            continue
        if hit.text in seen:
            continue
        seen.add(hit.text)
        hits.append(hit)
    return hits


def preceding_sloka_for_entry(entry: EntryHit, pages_jsonl: Path = PAGES_JSONL) -> SlokaHit | None:
    cross_indexed_hit = cross_indexed_sloka_for_entry(entry, pages_jsonl)
    if cross_indexed_hit:
        return cross_indexed_hit

    heading = entry.text.splitlines()[0].strip() if entry.text.splitlines() else ""
    if not heading:
        return None
    parsed_heading = parse_nama_heading(heading)
    heading_sanskrit, heading_roman = parsed_heading if parsed_heading else ("", "")

    pages = read_pages(pages_jsonl)
    for idx, page in enumerate(pages):
        if page.page != entry.page_start:
            continue
        page_text = normalize_text(page.text)
        heading_at = page_text.find(heading)
        if heading_at == -1:
            return None

        page_window = pages[max(0, idx - 8) : idx + 1]
        matched_blocks: list[tuple[int, int, SlokaHit]] = []
        for distance, candidate_page in enumerate(reversed(page_window)):
            candidate_text = normalize_text(candidate_page.text)
            for start, end, block in sloka_blocks(candidate_text):
                if candidate_page.page == page.page and start > heading_at:
                    continue
                if heading_sanskrit and sloka_matches_headword(block, heading_sanskrit, heading_roman):
                    matched_blocks.append(
                        (distance, max(0, heading_at - end) if candidate_page.page == page.page else 0,
                         SlokaHit(page=candidate_page.page, text=block, warnings=candidate_page.warnings))
                    )
        if matched_blocks:
            return sorted(matched_blocks, key=lambda item: (item[0], item[1]))[0][2]

        prior_blocks = [
            (start, end, block)
            for start, end, block in sloka_blocks(page_text)
            if end <= heading_at and heading_at - end < 2500
        ]
        if prior_blocks:
            _, _, block = prior_blocks[-1]
            return SlokaHit(page=page.page, text=block, warnings=page.warnings)

        if idx > 0:
            previous_page = pages[idx - 1]
            previous_blocks = sloka_blocks(normalize_text(previous_page.text))
            if previous_blocks:
                _, _, block = previous_blocks[-1]
                return SlokaHit(page=previous_page.page, text=block, warnings=previous_page.warnings)
        return None
    return None


def extract_entry(query: str, pages_jsonl: Path = PAGES_JSONL, window_after: int = 4) -> list[EntryHit]:
    pages = read_pages(pages_jsonl)
    needle = normalize_text(query)
    scored_hits: list[tuple[int, EntryHit]] = []
    seen_entries: set[tuple[int, int, str]] = set()

    for idx, page in enumerate(pages):
        page_text = normalize_text(page.text)
        occurrences: list[int] = []
        hit_at = page_text.find(needle)
        while hit_at != -1:
            occurrences.append(hit_at)
            hit_at = page_text.find(needle, hit_at + max(1, len(needle)))
        occurrences.extend(heading_occurrences(page_text, query))
        occurrences = sorted(set(occurrences))
        if not occurrences:
            continue

        for occurrence in occurrences:
            window_pages = pages[max(0, idx - 1) : min(len(pages), idx + window_after)]
            pieces: list[tuple[int, int, int, str]] = []
            combined = ""
            query_global_at: int | None = None
            for window_page in window_pages:
                start = len(combined)
                if combined:
                    combined += "\n\n"
                    start = len(combined)
                text = normalize_text(window_page.text)
                combined += text
                end = len(combined)
                pieces.append((window_page.page, start, end, text))
                if window_page.page == page.page:
                    query_global_at = start + occurrence

            if query_global_at is None:
                continue

            headings = [
                heading
                for heading in ENTRY_HEADING_RE.finditer(combined)
                if parse_nama_heading(heading.group(0))
            ]
            entry_start = 0
            for heading in headings:
                if heading.start() <= query_global_at:
                    entry_start = heading.start()
                else:
                    break

            entry_end = len(combined)
            for heading in headings:
                if heading.start() > max(entry_start, query_global_at):
                    entry_end = heading.start()
                    break

            entry_text = trim_trailing_verse_prelude(combined[entry_start:entry_end])
            if not entry_text:
                continue

            included_pages = [
                page_num
                for page_num, start, end, _ in pieces
                if start < entry_end and end > entry_start
            ]
            entry_key = (min(included_pages), max(included_pages), entry_text[:80])
            if entry_key in seen_entries:
                continue
            seen_entries.add(entry_key)

            warnings: list[str] = []
            for window_page in window_pages:
                if window_page.page in included_pages:
                    warnings.extend(window_page.warnings)

            scored_hits.append(
                (
                    max(0, query_global_at - entry_start),
                    EntryHit(
                    page_start=min(included_pages),
                    page_end=max(included_pages),
                    text=entry_text,
                    warnings=warnings,
                    ),
                )
            )

    results = [hit for _, hit in sorted(scored_hits, key=lambda item: item[0])]
    heading_results = [hit for hit in results if heading_matches_query(hit.text, query)]
    return heading_results or results


def passage_around(text: str, start: int, length: int, radius: int = 420) -> str:
    left = max(0, start - radius)
    right = min(len(text), start + length + radius)
    passage = text[left:right].strip()
    if left > 0:
        passage = re.sub(r"^\S*\s*", "", passage)
    if right < len(text):
        passage = re.sub(r"\s*\S*$", "", passage)
    return passage.strip()


def answer_from_hits(question: str, hits: list[SearchHit], sentence_limit: int = 5) -> str:
    sentences: list[tuple[int, str]] = []
    seen: set[str] = set()
    query_terms = set(tokenize(question))
    for hit in hits:
        parts = re.split(r"(?<=[.!?।॥])\s+|\n+", hit.text)
        ranked: list[tuple[int, str]] = []
        for part in parts:
            clean = part.strip()
            if len(clean) < 20 or clean in seen:
                continue
            overlap = len(query_terms.intersection(tokenize(clean)))
            ranked.append((overlap, clean))
        for _, sentence in sorted(ranked, key=lambda item: item[0], reverse=True)[:2]:
            seen.add(sentence)
            sentences.append((hit.page_start, sentence))
            if len(sentences) >= sentence_limit:
                break
        if len(sentences) >= sentence_limit:
            break
    if not sentences:
        return "No sufficiently grounded answer was found in the indexed PDF passages."
    lines = ["Grounded answer:"]
    for page, sentence in sentences:
        lines.append(f"- {sentence} [p. {page}]")
    return "\n".join(lines)
