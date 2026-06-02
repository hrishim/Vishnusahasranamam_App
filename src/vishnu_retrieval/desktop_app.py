from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from .io import INDEX_JSON, PAGES_JSONL
from .nama_index import numbers_for_devanagari_name
from .quality import audit_text
from .search import exact_search, extract_entry, hybrid_search, parse_nama_heading, preceding_sloka_for_entry, sloka_search


APP_TITLE = "Vishnusahasranamam"
HELP_TEXT = """Full Entry
Best for a nama/headword. It returns the containing śloka when available, then the complete extracted entry and stops at the next entry. If the same nama appears more than once, each numbered entry is shown separately.

Exact Search
Best for an exact Sanskrit or English word/phrase. It finds every direct occurrence in the text, shows nearby extracted text, and adds the containing śloka when the occurrence is inside one.

Sloka Search
Best for a word inside a śloka. It returns the full extracted śloka block, including the roman transliteration when available.

Hybrid Search
Best when you do not know the exact wording. It uses keyword plus related-text search to find likely passages.

Copy Output
Copies only the extracted passage text. Page and OCR notes are shown in the app but are not included in the copied text."""


@dataclass
class RenderedResult:
    display_text: str
    copy_text: str
    meta_text: str = ""


def citation(page_start: int, page_end: int | None = None) -> str:
    if page_end is None or page_start == page_end:
        return f"Page: {page_start}"
    return f"Pages: {page_start}-{page_end}"


def normalize_for_word(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    cleaned: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                cleaned.append("")
            blank = True
            continue
        cleaned.append(line)
        blank = False
    return "\n".join(cleaned).strip()


def useful_quality_notes(text: str, warnings: list[str]) -> list[str]:
    notes = list(dict.fromkeys(warnings))
    artifact_lines: list[int] = []
    for issue in audit_text(text, max_issues=20):
        if issue.kind == "sanskrit" or "artifact" in issue.message.casefold():
            artifact_lines.append(issue.line)
    if artifact_lines:
        lines = ", ".join(str(line) for line in sorted(set(artifact_lines)))
        notes.append(f"Possible OCR artifact on line(s): {lines}.")
    return notes


def append_notes(output: list[str], text: str, warnings: list[str]) -> None:
    notes = useful_quality_notes(text, warnings)
    output.extend(["", "OCR Notes:"])
    if notes:
        output.extend(f"- {note}" for note in notes)
    else:
        output.append("- No page-level OCR warning was reported.")


def metadata_text(
    text: str,
    warnings: list[str],
    page_start: int,
    page_end: int | None = None,
    nama_numbers: list[int] | None = None,
) -> str:
    parts: list[str] = []
    if nama_numbers:
        parts.append("Nama: " + ", ".join(str(number) for number in nama_numbers))
    parts.append(citation(page_start, page_end))
    notes = useful_quality_notes(text, warnings)
    if notes:
        parts.append("OCR: " + " ".join(notes))
    else:
        parts.append("OCR: no page-level warning")
    return " | ".join(parts)


def nama_numbers_for_entry_text(entry_text: str) -> list[int]:
    heading = entry_text.splitlines()[0].strip() if entry_text.splitlines() else ""
    heading_numbers = [int(number) for number in re.findall(r"\b\d{1,4}\b", heading) if 1 <= int(number) <= 1000]
    if heading_numbers:
        return sorted(set(heading_numbers))
    parsed = parse_nama_heading(heading)
    if not parsed:
        return []
    sanskrit, _ = parsed
    return numbers_for_devanagari_name(sanskrit)


def render_entry(query: str, top_k: int = 5) -> RenderedResult:
    hits = extract_entry(query, PAGES_JSONL, window_after=5)[:top_k]
    if not hits:
        return RenderedResult("No full entry found.", "")

    display_sections: list[str] = []
    copy_sections: list[str] = []
    meta_sections: list[str] = []
    for index, hit in enumerate(hits, start=1):
        body = normalize_for_word(hit.text)
        sloka_hit = preceding_sloka_for_entry(hit, PAGES_JSONL)
        sloka = normalize_for_word(sloka_hit.text) if sloka_hit else ""
        entry_body = "\n\n".join(part for part in (sloka, body) if part)
        combined_warnings = hit.warnings + (sloka_hit.warnings if sloka_hit else [])
        nama_numbers = nama_numbers_for_entry_text(hit.text)
        if len(hits) > 1:
            display_sections.append(f"Entry {index}\n\n{entry_body}")
            meta_sections.append(
                f"Entry {index}: {metadata_text(entry_body, combined_warnings, hit.page_start, hit.page_end, nama_numbers)}"
            )
        else:
            display_sections.append(entry_body)
            meta_sections.append(metadata_text(entry_body, combined_warnings, hit.page_start, hit.page_end, nama_numbers))
        copy_sections.append(entry_body)
    return RenderedResult("\n\n".join(display_sections), "\n\n".join(copy_sections), "\n".join(meta_sections))


def format_entry(query: str) -> str:
    return render_entry(query).display_text


def render_exact(query: str) -> RenderedResult:
    hits = exact_search(query, PAGES_JSONL, ignore_case=True)
    if not hits:
        return RenderedResult("No exact matches found.", "")

    sections: list[str] = []
    meta_sections: list[str] = []
    copy_sections: list[str] = []
    for i, hit in enumerate(hits[:10], start=1):
        passage = normalize_for_word(hit["passage"])
        sloka = normalize_for_word(hit["sloka"]) if hit.get("sloka") else ""
        display_parts: list[str] = []
        copy_parts: list[str] = []
        if sloka:
            display_parts.extend(["Sloka containing match", "", sloka, ""])
            copy_parts.append(sloka)
        display_parts.extend(["Exact passage", "", passage])
        copy_parts.append(passage)
        sections.append("\n".join(display_parts).strip())
        copy_sections.append("\n\n".join(copy_parts).strip())
        quality_text = "\n\n".join(part for part in (sloka, passage) if part)
        notes = useful_quality_notes(quality_text, hit.get("warnings", []))
        meta = f"Match {i}: Page: {hit['page']}"
        if notes:
            meta += " | OCR: " + " ".join(notes)
        meta_sections.append(meta)
    return RenderedResult("\n\n".join(sections), "\n\n".join(copy_sections), "\n".join(meta_sections))


def format_exact(query: str) -> str:
    return render_exact(query).display_text


def render_sloka(query: str) -> RenderedResult:
    hits = sloka_search(query, PAGES_JSONL, ignore_case=True)
    if not hits:
        return RenderedResult("No śloka found.", "")

    sections: list[str] = []
    meta_sections: list[str] = []
    copy_sections: list[str] = []
    for i, hit in enumerate(hits[:10], start=1):
        body = normalize_for_word(hit.text)
        if len(hits) > 1:
            sections.append(f"Sloka {i}\n\n{body}")
            meta_sections.append(f"Sloka {i}: {metadata_text(hit.text, hit.warnings, hit.page)}")
        else:
            sections.append(body)
            meta_sections.append(metadata_text(hit.text, hit.warnings, hit.page))
        copy_sections.append(body)
    return RenderedResult("\n\n".join(sections), "\n\n".join(copy_sections), "\n".join(meta_sections))


def format_sloka(query: str) -> str:
    return render_sloka(query).display_text


def render_hybrid(query: str) -> RenderedResult:
    hits = hybrid_search(query, INDEX_JSON, top_k=5)
    if not hits:
        return RenderedResult("No retrieval hits found.", "")

    sections: list[str] = []
    meta_sections: list[str] = []
    copy_sections: list[str] = []
    for i, hit in enumerate(hits, start=1):
        body = normalize_for_word(hit.text)
        output = [f"Result {i}", citation(hit.page_start, hit.page_end), "", body]
        append_notes(output, hit.text, hit.warnings)
        sections.append(body)
        copy_sections.append(body)
        meta_sections.append(f"Result {i}: {metadata_text(hit.text, hit.warnings, hit.page_start, hit.page_end)}")
    return RenderedResult("\n\n".join(sections), "\n\n".join(copy_sections), "\n".join(meta_sections))


def format_hybrid(query: str) -> str:
    return render_hybrid(query).display_text


def require_qt():
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import (
            QApplication,
            QButtonGroup,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QRadioButton,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "The desktop UI dependency is not installed. Install the desktop extra with: "
            "python -m pip install -e '.[desktop]'"
        ) from exc
    return {
        "Qt": Qt,
        "QFont": QFont,
        "QApplication": QApplication,
        "QButtonGroup": QButtonGroup,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QPushButton": QPushButton,
        "QRadioButton": QRadioButton,
        "QTextEdit": QTextEdit,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


def build_window(qt: dict):
    Qt = qt["Qt"]
    QFont = qt["QFont"]
    QApplication = qt["QApplication"]
    QButtonGroup = qt["QButtonGroup"]
    QTimer = __import__("PySide6.QtCore", fromlist=["QTimer"]).QTimer
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QMainWindow = qt["QMainWindow"]
    QMessageBox = qt["QMessageBox"]
    QPushButton = qt["QPushButton"]
    QRadioButton = qt["QRadioButton"]
    QTextEdit = qt["QTextEdit"]
    QVBoxLayout = qt["QVBoxLayout"]
    QWidget = qt["QWidget"]

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_TITLE)
            self.resize(1000, 740)
            self.setMinimumSize(760, 560)
            self.copy_text = ""

            root = QWidget()
            root.setObjectName("root")
            layout = QVBoxLayout(root)
            layout.setContentsMargins(26, 24, 26, 20)
            layout.setSpacing(14)

            title = QLabel("Vishnusahasranamam")
            title.setObjectName("title")
            subtitle = QLabel("Type a nāma or phrase. Results stay local and are formatted for copying into Word.")
            subtitle.setObjectName("subtitle")
            layout.addWidget(title)
            layout.addWidget(subtitle)

            search_row = QHBoxLayout()
            search_row.setSpacing(10)
            self.query = QLineEdit()
            self.query.setPlaceholderText("Example: ह्रीषीकेशः or Agrahyah")
            self.query.setClearButtonEnabled(True)
            self.query.returnPressed.connect(self.run_search)
            self.find_button = QPushButton("Find")
            self.find_button.setObjectName("primary")
            self.find_button.clicked.connect(self.run_search)
            search_row.addWidget(self.query, 1)
            search_row.addWidget(self.find_button)
            layout.addLayout(search_row)

            mode_row = QHBoxLayout()
            mode_row.setSpacing(18)
            self.mode_group = QButtonGroup(self)
            self.entry_mode = QRadioButton("Full Entry")
            self.exact_mode = QRadioButton("Exact Search")
            self.sloka_mode = QRadioButton("Sloka Search")
            self.hybrid_mode = QRadioButton("Hybrid Search")
            self.help_button = QPushButton("Help")
            self.entry_mode.setChecked(True)
            for button in (self.entry_mode, self.exact_mode, self.sloka_mode, self.hybrid_mode):
                self.mode_group.addButton(button)
                mode_row.addWidget(button)
            mode_row.addStretch(1)
            self.help_button.clicked.connect(self.show_help)
            mode_row.addWidget(self.help_button)
            layout.addLayout(mode_row)

            self.output = QTextEdit()
            self.output.setAcceptRichText(False)
            self.output.setReadOnly(True)
            self.output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.output.setFont(QFont("Arial Unicode MS", 18))
            layout.addWidget(self.output, 1)

            self.meta = QLabel("")
            self.meta.setObjectName("meta")
            self.meta.setWordWrap(True)
            layout.addWidget(self.meta)

            bottom = QHBoxLayout()
            bottom.setSpacing(10)
            copy_button = QPushButton("Copy Output")
            self.copy_button = copy_button
            copy_button.clicked.connect(self.copy_output)
            clear_button = QPushButton("Clear")
            clear_button.clicked.connect(self.clear)
            self.status = QLabel("Ready")
            self.status.setObjectName("status")
            self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bottom.addWidget(copy_button)
            bottom.addWidget(clear_button)
            bottom.addStretch(1)
            bottom.addWidget(self.status)
            layout.addLayout(bottom)

            self.setCentralWidget(root)
            self.setStyleSheet(
                """
                QWidget#root {
                    background: #f7f7f4;
                }
                QLabel#title {
                    color: #1f2933;
                    font-family: "Avenir Next";
                    font-size: 28px;
                    font-weight: 700;
                }
                QLabel#subtitle, QLabel#status {
                    color: #5d6673;
                    font-family: "Avenir Next";
                    font-size: 14px;
                }
                QLabel#meta {
                    color: #5d6673;
                    font-family: "Avenir Next";
                    font-size: 13px;
                    padding: 2px 2px 0 2px;
                }
                QLineEdit {
                    background: #ffffff;
                    color: #1d2329;
                    border: 1px solid #cfd4da;
                    border-radius: 6px;
                    padding: 10px 12px;
                    font-family: "Arial Unicode MS";
                    font-size: 18px;
                    selection-background-color: #b8d7ff;
                }
                QPushButton {
                    background: #ffffff;
                    color: #1f2933;
                    border: 1px solid #c8cdd3;
                    border-radius: 6px;
                    padding: 9px 16px;
                    font-family: "Avenir Next";
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #f0f3f6;
                }
                QPushButton#primary {
                    background: #244f7a;
                    color: #ffffff;
                    border: 1px solid #244f7a;
                    font-weight: 700;
                }
                QPushButton#primary:hover {
                    background: #1d4369;
                }
                QRadioButton {
                    color: #2b2f36;
                    font-family: "Avenir Next";
                    font-size: 14px;
                    spacing: 8px;
                }
                QTextEdit {
                    background: #ffffff;
                    color: #1d2329;
                    border: 1px solid #d6d8dc;
                    border-radius: 6px;
                    padding: 14px;
                    selection-background-color: #b8d7ff;
                }
                """
            )

        def run_search(self) -> None:
            query = self.query.text().strip()
            if not query:
                QMessageBox.information(self, APP_TITLE, "Please type a nāma or phrase first.")
                return

            self.status.setText("Searching...")
            QApplication.processEvents()
            try:
                if self.entry_mode.isChecked():
                    result = render_entry(query)
                elif self.exact_mode.isChecked():
                    result = render_exact(query)
                elif self.sloka_mode.isChecked():
                    result = render_sloka(query)
                else:
                    result = render_hybrid(query)
            except Exception as exc:  # pragma: no cover - UI safety net
                result = RenderedResult(f"Error: {exc}", "")
            self.output.setPlainText(result.display_text)
            self.copy_text = result.copy_text
            self.meta.setText(result.meta_text)
            self.status.setText("Ready")

        def copy_output(self) -> None:
            text = self.copy_text.strip()
            if not text:
                return
            QApplication.clipboard().setText(text)
            old_text = self.copy_button.text()
            self.copy_button.setText("Copied")
            self.status.setText("Copied to clipboard")
            QTimer.singleShot(1400, lambda: self.copy_button.setText(old_text))
            QTimer.singleShot(1400, lambda: self.status.setText("Ready"))

        def show_help(self) -> None:
            QMessageBox.information(self, "Search Options", HELP_TEXT)

        def clear(self) -> None:
            self.query.clear()
            self.output.clear()
            self.meta.clear()
            self.copy_text = ""
            self.status.setText("Ready")

    return MainWindow


def main() -> int:
    qt = require_qt()
    app = qt["QApplication"](sys.argv)
    window_class = build_window(qt)
    window = window_class()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
