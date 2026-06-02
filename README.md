# Vishnusahasranamam Retrieval Project

Local OCR, exact search, and hybrid retrieval for a scanned Vishnusahasranamam PDF with Devanagari Sanskrit and English.

## What It Supports

- OCR with Sanskrit Devanagari plus English using local Tesseract.
- Per-page text files and JSONL metadata with page numbers, line breaks, paragraph breaks, and confidence signals.
- Exact search for verbatim Sanskrit or English passages.
- Hybrid retrieval combining keyword scoring and vector similarity.
- Page-aware chunks with citations.
- Verbatim mode that returns only extracted PDF text.
- Answer mode that summarizes using only cited passages.
- OCR uncertainty warnings when confidence or extracted text density is weak.

## Setup

Tesseract and PDF rendering tools are already available on this machine. To create a Python environment:

```bash
cd /Users/sathyavasu/Projects/codex/Vishnusahasranamam
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

For stronger semantic embeddings later, install the optional local embedding stack:

```bash
python -m pip install -e ".[semantic]"
```

The project works without those optional packages by using a built-in local vector index.

## Chat-First Use

You do not need to run the scripts yourself. Put the scanned PDF in the project, then ask questions in Codex chat.

Examples:

- "Index the Vishnusahasranamam PDF."
- "Find the exact passage beginning with ..."
- "Return only the extracted Sanskrit text for the verse about ..."
- "Explain what pages 12-13 say about recitation, with citations."
- "Search for this English phrase exactly: ..."
- "Get the verbatim meaning of a name and check OCR spelling."

Codex defaults to verbatim extraction for all PDF questions. Ask for a summary, explanation, interpretation, comparison, or synthesis only when you want one.

Nama numbers are optional metadata. The auxiliary index PDF can be parsed into `data/index/nama_numbers.json`; rows with impossible OCR numbers are rejected instead of trusted.

Codex will use the local project tools internally and answer in chat with page citations.

## Add Your PDF

Place the scanned PDF here:

```text
/Users/sathyavasu/Projects/codex/Vishnusahasranamam/data/raw/Vishnusahasranamam.pdf
```

## Build OCR And Index

```bash
vishnu ingest data/raw/Vishnusahasranamam.pdf
```

Useful options:

```bash
vishnu ingest data/raw/Vishnusahasranamam.pdf --dpi 350 --langs san+eng
vishnu ocr data/raw/Vishnusahasranamam.pdf --from-page 1 --to-page 10
vishnu index
```

## Search

Exact search:

```bash
vishnu exact "धर्मक्षेत्रे"
vishnu exact "thousand names"
```

Hybrid retrieval:

```bash
vishnu search "meaning of Vishnu as the supreme self"
```

Verbatim mode:

```bash
vishnu search "विष्णोः नामानि" --verbatim
```

OCR spell-check/audit:

```bash
vishnu entry "प्रकाशात्मा" --spellcheck
vishnu spellcheck "प्रकाशात्मा" --entry
```

The audit keeps verbatim PDF text unchanged and reports likely OCR issues separately. English checks use the local system dictionary; Sanskrit/Devanagari checks conservatively flag mixed scripts, broken signs, and OCR artifact symbols rather than silently correcting Sanskrit.

Answer mode:

```bash
vishnu ask "What does the text say about reciting the names?"
```

Answer mode is intentionally citation-bound: it only uses retrieved passages from the scanned PDF.

## Local Web App / PWA

The project also includes a local browser app. It uses the same local index and does not send the text to any external service.

Start it with:

```bash
vishnu-web --host 0.0.0.0 --port 8765 --open
```

Or double-click:

```text
Run Vishnusahasranamam Web.command
```

On the Mac, open:

```text
http://127.0.0.1:8765
```

From an iPhone or iPad on the same Wi-Fi, open the same-Wi-Fi URL printed by the launcher, then use Safari's Share button and choose Add to Home Screen. Full offline PWA caching on iOS may require HTTPS, but normal local searching works while the Mac server is running.

## Output Files

- `data/ocr/pages.jsonl`: extracted page text, confidence, warnings.
- `data/ocr/pages/page_0001.txt`: one text file per page.
- `data/index/index.json`: chunks, keyword stats, and vector data.
