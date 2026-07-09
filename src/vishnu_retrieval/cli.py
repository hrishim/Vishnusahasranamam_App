from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .docx_source import run_docx_ingest
from .epub_source import run_epub_ingest
from .indexer import build_index
from .io import INDEX_JSON, NAMA_NUMBERS_JSON, PAGES_JSONL
from .nama_index import build_nama_number_index, numbers_for_devanagari_name
from .ocr import run_ocr
from .quality import audit_text, format_quality_issues
from .search import answer_from_hits, exact_search, extract_entry, hybrid_search, sloka_search


def print_warning_lines(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"  OCR warning: {warning}")


def cmd_check(_: argparse.Namespace) -> int:
    checks = {
        "tesseract": shutil.which("tesseract"),
        "pdftoppm": shutil.which("pdftoppm"),
        "pdfinfo": shutil.which("pdfinfo"),
    }
    for name, path in checks.items():
        status = path or "missing"
        print(f"{name}: {status}")
    missing = [name for name, path in checks.items() if not path]
    if missing:
        return 1
    return 0


def cmd_ocr(args: argparse.Namespace) -> int:
    records = run_ocr(
        Path(args.pdf),
        Path(args.out),
        from_page=args.from_page,
        to_page=args.to_page,
        dpi=args.dpi,
        langs=args.langs,
        psm=args.psm,
        mode=args.mode,
    )
    print(f"OCR complete: {len(records)} pages -> {args.out}")
    warned = sum(1 for record in records if record.warnings)
    if warned:
        print(f"OCR warnings on {warned} pages. Inspect data/ocr/pages.jsonl for details.")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    index = build_index(Path(args.pages), Path(args.out), max_chars=args.max_chars, overlap=args.overlap)
    print(f"Index complete: {index['chunk_count']} chunks -> {args.out}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    ocr_args = argparse.Namespace(**vars(args), out=str(PAGES_JSONL))
    cmd_ocr(ocr_args)
    index = build_index(PAGES_JSONL, INDEX_JSON, max_chars=args.max_chars, overlap=args.overlap)
    print(f"Index complete: {index['chunk_count']} chunks -> {INDEX_JSON}")
    return 0


def cmd_docx_ingest(args: argparse.Namespace) -> int:
    records = run_docx_ingest(
        Path(args.docx),
        PAGES_JSONL,
        pdf_path=Path(args.pdf) if args.pdf else None,
        alignment_pages_jsonl=Path(args.alignment_pages),
    )
    print(f"DOCX extraction complete: {len(records)} logical pages -> {PAGES_JSONL}")
    inferred = sum(1 for record in records if record.warnings)
    if inferred:
        print(f"PDF citation alignment warnings on {inferred} logical pages.")
    index = build_index(PAGES_JSONL, INDEX_JSON, max_chars=args.max_chars, overlap=args.overlap)
    print(f"Index complete: {index['chunk_count']} chunks -> {INDEX_JSON}")
    return 0


def cmd_epub_ingest(args: argparse.Namespace) -> int:
    records = run_epub_ingest(
        Path(args.epub),
        PAGES_JSONL,
        pdf_path=Path(args.pdf) if args.pdf else None,
        alignment_pages_jsonl=Path(args.alignment_pages),
    )
    print(f"EPUB extraction complete: {len(records)} aligned pages -> {PAGES_JSONL}")
    index = build_index(PAGES_JSONL, INDEX_JSON, max_chars=args.max_chars, overlap=args.overlap)
    print(f"Index complete: {index['chunk_count']} chunks -> {INDEX_JSON}")
    return 0


def cmd_nama_index(args: argparse.Namespace) -> int:
    payload = build_nama_number_index(Path(args.pdf), Path(args.out))
    print(f"Nama number index complete: {payload['parsed_name_count']} names -> {args.out}")
    print(f"Covered nama numbers: {payload['covered_number_count']} of 1000")
    rejected = len(payload.get("rejected_rows", []))
    if rejected:
        print(f"Rejected likely OCR-bad rows: {rejected}")
    return 0


def cmd_nama_number(args: argparse.Namespace) -> int:
    numbers = numbers_for_devanagari_name(args.query, Path(args.index))
    if not numbers:
        print("No nama number found in the auxiliary index.")
        return 0
    print(", ".join(str(number) for number in numbers))
    return 0


def cmd_exact(args: argparse.Namespace) -> int:
    hits = exact_search(args.query, Path(args.pages), ignore_case=args.ignore_case)
    if not hits:
        print("No exact matches found.")
        return 0
    for i, hit in enumerate(hits[: args.top_k], start=1):
        print(f"\n[{i}] p. {hit['page']}")
        print(hit["passage"])
        print_warning_lines(hit.get("warnings", []))
    return 0


def cmd_sloka(args: argparse.Namespace) -> int:
    hits = sloka_search(args.query, Path(args.pages), ignore_case=args.ignore_case)
    if not hits:
        print("No sloka found.")
        return 0
    for i, hit in enumerate(hits[: args.top_k], start=1):
        print(f"\n[{i}] p. {hit.page}")
        print(hit.text)
        print_warning_lines(hit.warnings)
    return 0


def cmd_entry(args: argparse.Namespace) -> int:
    hits = extract_entry(args.query, Path(args.pages), window_after=args.window_after)
    if not hits:
        print("No full entry found.")
        return 0
    for i, hit in enumerate(hits[: args.top_k], start=1):
        citation = f"p. {hit.page_start}" if hit.page_start == hit.page_end else f"pp. {hit.page_start}-{hit.page_end}"
        print(f"\n[{i}] {citation}")
        print(hit.text)
        print_warning_lines(hit.warnings)
        if args.spellcheck:
            print()
            print(format_quality_issues(audit_text(hit.text)))
    return 0


def cmd_spellcheck(args: argparse.Namespace) -> int:
    if args.entry:
        hits = extract_entry(args.query, Path(args.pages), window_after=args.window_after)
        if not hits:
            print("No full entry found.")
            return 0
        for i, hit in enumerate(hits[: args.top_k], start=1):
            citation = f"p. {hit.page_start}" if hit.page_start == hit.page_end else f"pp. {hit.page_start}-{hit.page_end}"
            print(f"\n[{i}] {citation}")
            print(format_quality_issues(audit_text(hit.text, max_issues=args.max_issues)))
        return 0

    hits = hybrid_search(args.query, Path(args.index), top_k=args.top_k)
    if not hits:
        print("No retrieval hits found.")
        return 0
    for i, hit in enumerate(hits, start=1):
        citation = f"p. {hit.page_start}" if hit.page_start == hit.page_end else f"pp. {hit.page_start}-{hit.page_end}"
        print(f"\n[{i}] {citation}")
        print(format_quality_issues(audit_text(hit.text, max_issues=args.max_issues)))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    hits = hybrid_search(
        args.query,
        Path(args.index),
        top_k=args.top_k,
        keyword_weight=args.keyword_weight,
        vector_weight=args.vector_weight,
    )
    if not hits:
        print("No retrieval hits found.")
        return 0
    for i, hit in enumerate(hits, start=1):
        citation = f"p. {hit.page_start}" if hit.page_start == hit.page_end else f"pp. {hit.page_start}-{hit.page_end}"
        if args.verbatim:
            print(f"\n[{i}] {citation}")
            print(hit.text)
        else:
            print(f"\n[{i}] {citation} | score={hit.score:.3f} keyword={hit.keyword_score:.3f} vector={hit.vector_score:.3f}")
            print(hit.text)
        print_warning_lines(hit.warnings)
        if args.spellcheck:
            print()
            print(format_quality_issues(audit_text(hit.text)))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    hits = hybrid_search(args.question, Path(args.index), top_k=args.top_k)
    print(answer_from_hits(args.question, hits, sentence_limit=args.sentences))
    if hits:
        print("\nCited passages:")
        for i, hit in enumerate(hits, start=1):
            citation = f"p. {hit.page_start}" if hit.page_start == hit.page_end else f"pp. {hit.page_start}-{hit.page_end}"
            print(f"\n[{i}] {citation}")
            print(hit.text)
            print_warning_lines(hit.warnings)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vishnu", description="OCR and retrieve from the scanned Vishnusahasranamam PDF.")
    sub = parser.add_subparsers(required=True)

    check = sub.add_parser("check", help="Check local OCR dependencies.")
    check.set_defaults(func=cmd_check)

    ocr = sub.add_parser("ocr", help="Extract OCR text from a scanned PDF.")
    ocr.add_argument("pdf")
    ocr.add_argument("--out", default=str(PAGES_JSONL))
    ocr.add_argument("--from-page", type=int)
    ocr.add_argument("--to-page", type=int)
    ocr.add_argument("--dpi", type=int, default=350)
    ocr.add_argument("--langs", default="san+eng")
    ocr.add_argument("--psm", type=int, default=6)
    ocr.add_argument("--mode", choices=["auto", "embedded", "ocr"], default="auto")
    ocr.set_defaults(func=cmd_ocr)

    index = sub.add_parser("index", help="Build page-aware chunks and retrieval index.")
    index.add_argument("--pages", default=str(PAGES_JSONL))
    index.add_argument("--out", default=str(INDEX_JSON))
    index.add_argument("--max-chars", type=int, default=1200)
    index.add_argument("--overlap", type=int, default=180)
    index.set_defaults(func=cmd_index)

    ingest = sub.add_parser("ingest", help="Run OCR and build the index.")
    ingest.add_argument("pdf")
    ingest.add_argument("--from-page", type=int)
    ingest.add_argument("--to-page", type=int)
    ingest.add_argument("--dpi", type=int, default=350)
    ingest.add_argument("--langs", default="san+eng")
    ingest.add_argument("--psm", type=int, default=6)
    ingest.add_argument("--mode", choices=["auto", "embedded", "ocr"], default="auto")
    ingest.add_argument("--max-chars", type=int, default=1200)
    ingest.add_argument("--overlap", type=int, default=180)
    ingest.set_defaults(func=cmd_ingest)

    docx_ingest = sub.add_parser("docx-ingest", help="Build clean text and retrieval index from a DOCX source.")
    docx_ingest.add_argument("docx")
    docx_ingest.add_argument("--pdf", help="PDF path used only for source/citation metadata.")
    docx_ingest.add_argument(
        "--alignment-pages",
        default=str(PAGES_JSONL),
        help="Existing PDF OCR JSONL used to align DOCX book-page markers to PDF page citations.",
    )
    docx_ingest.add_argument("--max-chars", type=int, default=1200)
    docx_ingest.add_argument("--overlap", type=int, default=180)
    docx_ingest.set_defaults(func=cmd_docx_ingest)

    epub_ingest = sub.add_parser("epub-ingest", help="Build clean text and retrieval index from an EPUB source.")
    epub_ingest.add_argument("epub")
    epub_ingest.add_argument("--pdf", help="PDF path used only for source/citation metadata.")
    epub_ingest.add_argument(
        "--alignment-pages",
        default=str(PAGES_JSONL),
        help="Existing page JSONL used to align EPUB paragraphs to citation pages.",
    )
    epub_ingest.add_argument("--max-chars", type=int, default=1200)
    epub_ingest.add_argument("--overlap", type=int, default=180)
    epub_ingest.set_defaults(func=cmd_epub_ingest)

    nama_index = sub.add_parser("nama-index", help="Build an auxiliary Devanagari name-to-nama-number index.")
    nama_index.add_argument("pdf")
    nama_index.add_argument("--out", default=str(NAMA_NUMBERS_JSON))
    nama_index.set_defaults(func=cmd_nama_index)

    nama_number = sub.add_parser("nama-number", help="Look up nama numbers from the auxiliary index.")
    nama_number.add_argument("query")
    nama_number.add_argument("--index", default=str(NAMA_NUMBERS_JSON))
    nama_number.set_defaults(func=cmd_nama_number)

    exact = sub.add_parser("exact", help="Exact verbatim passage search.")
    exact.add_argument("query")
    exact.add_argument("--pages", default=str(PAGES_JSONL))
    exact.add_argument("--top-k", type=int, default=20)
    exact.add_argument("--ignore-case", action="store_true")
    exact.set_defaults(func=cmd_exact)

    sloka = sub.add_parser("sloka", help="Find full extracted sloka blocks containing a word or phrase.")
    sloka.add_argument("query")
    sloka.add_argument("--pages", default=str(PAGES_JSONL))
    sloka.add_argument("--top-k", type=int, default=20)
    sloka.add_argument("--ignore-case", action="store_true", default=True)
    sloka.set_defaults(func=cmd_sloka)

    entry = sub.add_parser("entry", help="Extract the full numbered entry containing a headword.")
    entry.add_argument("query")
    entry.add_argument("--pages", default=str(PAGES_JSONL))
    entry.add_argument("--top-k", type=int, default=5)
    entry.add_argument("--window-after", type=int, default=5)
    entry.add_argument("--spellcheck", action="store_true")
    entry.set_defaults(func=cmd_entry)

    spellcheck = sub.add_parser("spellcheck", help="Audit OCR spelling/quality for English and Devanagari Sanskrit.")
    spellcheck.add_argument("query")
    spellcheck.add_argument("--entry", action="store_true", help="Audit the full numbered entry containing the query.")
    spellcheck.add_argument("--pages", default=str(PAGES_JSONL))
    spellcheck.add_argument("--index", default=str(INDEX_JSON))
    spellcheck.add_argument("--top-k", type=int, default=5)
    spellcheck.add_argument("--window-after", type=int, default=5)
    spellcheck.add_argument("--max-issues", type=int, default=40)
    spellcheck.set_defaults(func=cmd_spellcheck)

    search = sub.add_parser("search", help="Hybrid keyword plus vector retrieval.")
    search.add_argument("query")
    search.add_argument("--index", default=str(INDEX_JSON))
    search.add_argument("--top-k", type=int, default=8)
    search.add_argument("--keyword-weight", type=float, default=0.55)
    search.add_argument("--vector-weight", type=float, default=0.45)
    search.add_argument("--verbatim", action="store_true")
    search.add_argument("--spellcheck", action="store_true")
    search.set_defaults(func=cmd_search)

    ask = sub.add_parser("ask", help="Answer using only cited PDF passages.")
    ask.add_argument("question")
    ask.add_argument("--index", default=str(INDEX_JSON))
    ask.add_argument("--top-k", type=int, default=5)
    ask.add_argument("--sentences", type=int, default=5)
    ask.set_defaults(func=cmd_ask)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
