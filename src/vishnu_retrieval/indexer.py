from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

from .io import INDEX_JSON, PAGES_JSONL, read_pages, write_index
from .models import ChunkRecord, PageRecord
from .textutil import paragraph_blocks, sparse_vector, tokenize


def chunk_page(page: PageRecord, max_chars: int = 1200, overlap: int = 180) -> list[str]:
    chunks: list[str] = []
    current = ""
    for block in paragraph_blocks(page.text):
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(block) <= max_chars:
            current = block
        else:
            start = 0
            while start < len(block):
                chunk = block[start : start + max_chars].strip()
                if chunk:
                    chunks.append(chunk)
                start += max_chars - overlap
            current = ""
    if current:
        chunks.append(current)
    return chunks


def build_chunks(pages: list[PageRecord], max_chars: int = 1200, overlap: int = 180) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    for page in pages:
        for idx, text in enumerate(chunk_page(page, max_chars=max_chars, overlap=overlap), start=1):
            tokens = tokenize(text)
            chunks.append(
                ChunkRecord(
                    chunk_id=f"p{page.page:04d}-c{idx:03d}",
                    text=text,
                    pages=[page.page],
                    page_start=page.page,
                    page_end=page.page,
                    avg_confidence=page.avg_confidence,
                    warnings=page.warnings.copy(),
                    token_count=len(tokens),
                    vector=sparse_vector(text),
                )
            )
    return chunks


def build_keyword_stats(chunks: list[ChunkRecord]) -> dict:
    doc_freq: dict[str, int] = defaultdict(int)
    lengths: list[int] = []
    for chunk in chunks:
        tokens = tokenize(chunk.text)
        lengths.append(len(tokens))
        for token in set(tokens):
            doc_freq[token] += 1
    return {
        "doc_freq": dict(doc_freq),
        "avg_doc_len": sum(lengths) / len(lengths) if lengths else 0.0,
        "doc_count": len(chunks),
    }


def keyword_score(query_tokens: list[str], text: str, stats: dict) -> float:
    if not query_tokens:
        return 0.0
    tokens = tokenize(text)
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    doc_count = stats.get("doc_count", 0) or 1
    avgdl = stats.get("avg_doc_len", 0.0) or len(tokens)
    k1 = 1.4
    b = 0.75
    score = 0.0
    for token in query_tokens:
        tf = counts.get(token, 0)
        if not tf:
            continue
        df = stats.get("doc_freq", {}).get(token, 0)
        idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
        denom = tf + k1 * (1 - b + b * len(tokens) / avgdl)
        score += idf * (tf * (k1 + 1) / denom)
    return score


def build_index(
    pages_jsonl: Path = PAGES_JSONL,
    out_path: Path = INDEX_JSON,
    max_chars: int = 1200,
    overlap: int = 180,
) -> dict:
    pages = read_pages(pages_jsonl)
    chunks = build_chunks(pages, max_chars=max_chars, overlap=overlap)
    stats = build_keyword_stats(chunks)
    source_pdfs = sorted({page.source_pdf for page in pages})
    source_hashes = sorted({page.source_sha256 for page in pages})
    source_docxs = sorted({page.source_docx for page in pages if page.source_docx})
    index = {
        "schema_version": 1,
        "source_pdf": source_pdfs[0] if len(source_pdfs) == 1 else None,
        "source_pdfs": source_pdfs,
        "source_docx": source_docxs[0] if len(source_docxs) == 1 else None,
        "source_docxs": source_docxs,
        "source_sha256": source_hashes[0] if len(source_hashes) == 1 else None,
        "source_sha256s": source_hashes,
        "chunk_count": len(chunks),
        "keyword": stats,
        "chunks": [chunk.to_json() for chunk in chunks],
    }
    write_index(index, out_path)
    return index
