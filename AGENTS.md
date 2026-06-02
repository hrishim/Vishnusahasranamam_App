# Vishnusahasranamam Project Notes

This project is for local, page-aware retrieval over a scanned PDF containing Devanagari Sanskrit and English.

Core rules:
- Preserve page numbers and extracted line/paragraph boundaries wherever possible.
- In verbatim mode, return only text extracted from the PDF, with page citations.
- In answer mode, explanations must be grounded in cited page passages.
- Warn when OCR confidence is low or when a page/chunk has unusually sparse text.
- Prefer local processing. Do not send scanned text to external APIs unless explicitly requested.

User-facing workflow:
- The user wants to ask questions in Codex chat, not run scripts directly.
- Treat `.venv/bin/vishnu` as an internal tool for OCR, indexing, exact search, retrieval, and cited answers.
- Do not tell the user to run `vishnu` unless they explicitly ask for command-line details.
- When the user drops in a PDF and asks a question, first check whether `data/ocr/pages.jsonl` and `data/index/index.json` exist for that PDF. If not, run ingestion internally.
- Default to verbatim extraction for all user requests against the PDF: name meanings, passages, page lookups, search results, definitions, and answers.
- Do not summarize, explain, paraphrase, interpret, or merge passages unless the user explicitly asks for summary, explanation, interpretation, comparison, or synthesis.
- For specific sahasranama headwords, use full-entry extraction first, so the answer spans page breaks and stops at the next numbered entry.
- Nama numbers are optional metadata from `data/index/nama_numbers.json`. Use them only as auxiliary information and do not let them control retrieval. If a number is absent or rejected as OCR-bad, omit it or say the auxiliary index did not safely provide it.
- For default/verbatim requests, return extracted PDF text and page citations, followed by separate OCR notes if needed.
- When using OCR-derived text, run or mentally apply the spell/OCR audit for both English and Sanskrit/Devanagari. Keep verbatim text unchanged, but separately flag likely OCR spelling issues and obvious probable corrections.
- For explanatory requests, answer briefly and cite the retrieved passages/pages used.
- If retrieval depends on questionable OCR, include a plain-language warning.
