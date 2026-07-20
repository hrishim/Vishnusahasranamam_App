from __future__ import annotations

import re
import sys
import json
from html import escape
from dataclasses import dataclass
from functools import lru_cache

from .canonical import canonical_by_number
from .corrections import apply_curated_corrections
from .io import DERIVATION_OVERRIDES_JSON, PAGES_JSONL
from .nama_index import numbers_for_devanagari_name
from .quality import audit_text
from .search import (
    answer_from_hits,
    exact_search,
    extract_entry,
    hybrid_search,
    parse_nama_heading,
    preceding_sloka_for_entry,
    sloka_search,
    strong_hits,
    roman_match_key,
)


APP_TITLE = "Vishnusahasranamam"
HELP_TEXT = """Nāma Search
Best for one of the 1000 names. Type Devanagari or Roman text such as प्राणदः, Madhava, or Hrisikesa. It returns the complete verified entry.

Exact Text
Best for an exact Sanskrit or English word or phrase. It shows the direct passage and the containing śloka when available.

Śloka
Best for a śloka number from 1 to 108. Type 78 or śloka 78.

Question
Best for a simple question. It gives a short answer only when the matching passage is strong enough.

Copy
Copies the result text without internal notes."""


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
    text = apply_curated_corrections(text)
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


def _has_devanagari(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", text))


def _looks_like_transliteration(text: str) -> bool:
    clean = text.strip()
    english_words = re.compile(
        r"\b(the|one|who|word|means|lord|being|because|since|therefore|where|when|which|this|that|with|from|into|everything|pervades|if|then|does|not|know|knows|himself|herself|continues|form|other|until|every|all|called|there|are|is|as|it|he|she|you|we|they|their|his|her|in|of|and|or|to|by|for|on|basis|few|verses)\b",
        re.IGNORECASE,
    )
    if english_words.search(clean):
        return False
    words = re.findall(r"[A-Za-zāīūṛṝḷṅñṭḍṇśṣḥṃĀĪŪṚṜḶṄÑṬḌṆŚṢḤ]+", clean)
    if len(words) > 9:
        return False
    return bool(re.search(r"[āīūṛṝḷṅñṭḍṇśṣḥṃ]", clean, re.IGNORECASE)) and not re.search(r"[.!?]$", clean)


def _append_paragraphs(parts: list[str], html_parts: list[str]) -> None:
    clean = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if not clean:
        return
    sentences = re.findall(r"[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$", clean) or [clean]
    current = ""
    for part in sentences:
        sentence = part.strip()
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > 520:
            html_parts.append(f'<p class="para">{escape(current)}</p>')
            current = sentence
        else:
            current = candidate
    if current:
        html_parts.append(f'<p class="para">{escape(current)}</p>')


def display_text_to_html(text: str) -> str:
    html_parts = [
        """
        <style>
          body { color: #18222f; font-family: "Avenir Next", -apple-system, sans-serif; font-size: 16px; line-height: 1.42; }
          h2 { margin: 0 0 14px; font-size: 19px; font-weight: 700; }
          h3 { margin: 16px 0 8px; font-size: 17px; font-weight: 700; }
          p.para { margin: 0 0 12px; }
          div.script { margin: 0 0 7px; font-family: "Arial Unicode MS", "Devanagari Sangam MN", serif; font-size: 18px; line-height: 1.55; }
          div.translit { margin: 0 0 7px; color: #425066; font-family: "Arial Unicode MS", serif; font-size: 16px; line-height: 1.38; }
        </style>
        """
    ]
    paragraph: list[str] = []

    def flush() -> None:
        nonlocal paragraph
        _append_paragraphs(paragraph, html_parts)
        paragraph = []

    for raw_line in str(text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            last = paragraph[-1] if paragraph else ""
            if last and not re.search(r"[.!?।॥:'”)]$", last):
                continue
            flush()
            continue
        if re.match(r"^(Entry|Match)\s+\d+\b", line):
            flush()
            html_parts.append(f"<h2>{escape(line)}</h2>")
        elif re.match(r"^(Answer|Śloka)\b", line):
            flush()
            html_parts.append(f"<h3>{escape(line)}</h3>")
        elif line.startswith("- "):
            flush()
            html_parts.append(f'<p class="para">• {escape(line[2:].strip())}</p>')
        elif _has_devanagari(line):
            flush()
            html_parts.append(f'<div class="script">{escape(line)}</div>')
        elif _looks_like_transliteration(line):
            flush()
            html_parts.append(f'<div class="translit">{escape(line)}</div>')
        else:
            paragraph.append(line)
    flush()
    return "\n".join(html_parts)


def useful_quality_notes(text: str, warnings: list[str]) -> list[str]:
    notes = list(dict.fromkeys(warnings))
    artifact_lines: list[int] = []
    for issue in audit_text(text, max_issues=20):
        if issue.kind == "sanskrit" or "artifact" in issue.message.casefold():
            artifact_lines.append(issue.line)
    if artifact_lines:
        lines = ", ".join(str(line) for line in sorted(set(artifact_lines)))
        notes.append(f"Please check extracted text on line(s): {lines}.")
    return notes


def source_text(
    page_start: int,
    page_end: int | None = None,
    nama_numbers: list[int] | None = None,
    include_page: bool = False,
) -> str:
    parts: list[str] = []
    if nama_numbers:
        parts.append("Nama: " + ", ".join(str(number) for number in nama_numbers))
    if include_page:
        parts.append(citation(page_start, page_end))
    return " | ".join(parts)


def caution_text(label: str, text: str, warnings: list[str]) -> str:
    return ""


def hide_page_references(text: str) -> str:
    return re.sub(r"\s*\[p\. \d+\]", "", text)


@lru_cache(maxsize=1)
def derivation_overrides() -> dict[str, str]:
    if not DERIVATION_OVERRIDES_JSON.exists():
        return {}
    payload = json.loads(DERIVATION_OVERRIDES_JSON.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in payload.get("overrides", {}).items()}


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


def clean_entry_heading(hit) -> str:
    if hit.number is None:
        return ""
    row = canonical_by_number(hit.number)
    if not row:
        return ""
    devanagari = row.get("devanagari", "").strip()
    roman = row.get("roman", "").strip()
    if devanagari:
        return f"{devanagari} ({hit.number})"
    return f"{roman or devanagari} ({hit.number})".strip()


def is_page_artifact_line(line: str) -> bool:
    stripped = line.strip()
    if re.fullmatch(r"\d{1,4}", stripped):
        return True
    if re.fullmatch(r"\d{1,4}\s*\|\s*VI[ṢS][ṆN]USAHASRANAMA", stripped, re.IGNORECASE):
        return True
    return stripped.upper() in {"VISNUSAHASRANAMA", "VIṢṆUSAHASRANAMA", "VISHNUSAHASRANAMA"}


def has_near_heading_derivation(lines: list[str]) -> bool:
    for line in lines[1:5]:
        if re.search(r"[\u0900-\u097F]", line) and len(re.findall(r"[\u0900-\u097F]", line)) >= 8:
            return True
    return False


def insert_derivation_override(lines: list[str], hit) -> list[str]:
    if hit.number is None or len(lines) < 2 or has_near_heading_derivation(lines):
        return lines
    row = canonical_by_number(hit.number)
    if not row:
        return lines
    override = derivation_overrides().get(roman_match_key(row.get("roman", "")))
    if not override:
        return lines
    rest = lines[1:]
    while rest:
        line = rest[0].strip()
        if not line:
            rest = rest[1:]
            continue
        has_devanagari = bool(re.search(r"[\u0900-\u097F]", line))
        has_latin = bool(re.search(r"[A-Za-z]", line))
        devanagari_count = len(re.findall(r"[\u0900-\u097F]", line))
        if has_devanagari and not has_latin and devanagari_count < 8:
            rest = rest[1:]
            continue
        break
    return [lines[0], override, *rest]


def remove_top_broken_fragments(lines: list[str]) -> list[str]:
    if len(lines) < 2:
        return lines
    rest = lines[1:]
    cleaned_rest: list[str] = []
    scanning_top = True
    for line in rest:
        stripped = line.strip()
        if scanning_top and not stripped:
            continue
        has_devanagari = bool(re.search(r"[\u0900-\u097F]", stripped))
        has_latin = bool(re.search(r"[A-Za-z]", stripped))
        devanagari_count = len(re.findall(r"[\u0900-\u097F]", stripped))
        if scanning_top and has_devanagari and not has_latin and devanagari_count < 8:
            continue
        scanning_top = False
        cleaned_rest.append(line)
    return [lines[0], *cleaned_rest]


def entry_body_with_clean_heading(hit) -> str:
    body = normalize_for_word(hit.text)
    clean_heading = clean_entry_heading(hit)
    if not clean_heading:
        return body
    lines = body.splitlines()
    if lines:
        cleaned_lines = [clean_heading]
        index = 1
        while index < len(lines):
            line = lines[index].strip()
            if not line:
                index += 1
                continue
            has_devanagari = bool(re.search(r"[\u0900-\u097F]", line))
            has_latin = bool(re.search(r"[A-Za-z]", line))
            if has_devanagari and not has_latin and len(line) <= 40:
                index += 1
                continue
            break
        cleaned_lines.extend(line for line in lines[index:] if not is_page_artifact_line(line))
        lines = remove_top_broken_fragments(insert_derivation_override(cleaned_lines, hit))
        return "\n".join(lines).strip()
    return clean_heading


def render_entry(query: str, top_k: int = 5) -> RenderedResult:
    hits = extract_entry(query, PAGES_JSONL, window_after=5)[:top_k]
    if not hits:
        return RenderedResult("No full entry found.", "")

    display_sections: list[str] = []
    copy_sections: list[str] = []
    for index, hit in enumerate(hits, start=1):
        body = entry_body_with_clean_heading(hit)
        sloka_hit = preceding_sloka_for_entry(hit, PAGES_JSONL)
        sloka = normalize_for_word(sloka_hit.text) if sloka_hit else ""
        entry_body = "\n\n".join(part for part in (sloka, body) if part)
        nama_numbers = [hit.number] if hit.number is not None else nama_numbers_for_entry_text(hit.text)
        entry_source = source_text(hit.page_start, hit.page_end, nama_numbers)
        heading = f"Entry {index}"
        if entry_source:
            heading += f" - {entry_source}"
        display_sections.append(f"{heading}\n\n{entry_body}")
        copy_sections.append(entry_body)
    return RenderedResult("\n\n".join(display_sections), "\n\n".join(copy_sections))


def format_entry(query: str) -> str:
    return render_entry(query).display_text


def render_exact(query: str) -> RenderedResult:
    hits = exact_search(query, PAGES_JSONL, ignore_case=True)
    if not hits:
        entry_result = render_entry(query, top_k=5)
        if entry_result.copy_text:
            display_text = "No exact text match was found. Showing the verified nāma entry instead.\n\n"
            return RenderedResult(
                display_text + entry_result.display_text,
                entry_result.copy_text,
            )
        return RenderedResult("No exact text match found.", "")

    sections: list[str] = []
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
        sections[-1] = f"Match {i}\n\n{sections[-1]}"
    return RenderedResult("\n\n".join(sections), "\n\n".join(copy_sections))


def format_exact(query: str) -> str:
    return render_exact(query).display_text


def render_sloka(query: str) -> RenderedResult:
    hits = sloka_search(query, PAGES_JSONL, ignore_case=True)
    if not hits:
        return RenderedResult("No śloka match found.", "")

    sections: list[str] = []
    copy_sections: list[str] = []
    for i, hit in enumerate(hits[:10], start=1):
        body = normalize_for_word(hit.text)
        sections.append(f"Sloka {i}\n\n{body}")
        copy_sections.append(body)
    return RenderedResult("\n\n".join(sections), "\n\n".join(copy_sections))


def format_sloka(query: str) -> str:
    return render_sloka(query).display_text


def render_hybrid(query: str, top_k: int = 3) -> RenderedResult:
    hits = strong_hits(hybrid_search(query, top_k=max(8, top_k)), top_k=top_k)
    if not hits:
        return RenderedResult("No clear passage match found.", "")

    sections: list[str] = []
    copy_sections: list[str] = []
    for i, hit in enumerate(hits, start=1):
        body = normalize_for_word(hit.text)
        heading = f"Source passage {i}"
        sections.append(f"{heading}\n\n{body}")
        copy_sections.append(f"{heading}\n\n{body}")
    return RenderedResult("\n\n".join(sections), "\n\n".join(copy_sections))


def render_answer(query: str, top_k: int = 3) -> RenderedResult:
    hits = strong_hits(hybrid_search(query, top_k=max(8, top_k)), top_k=top_k)
    if not hits or hits[0].keyword_score <= 0 or hits[0].score < 0.40:
        message = "No clear answer found in this text."
        return RenderedResult(message, message)

    answer = answer_from_hits(query, hits)
    if answer.startswith("No sufficiently grounded"):
        message = "No clear answer found in this text."
        return RenderedResult(message, message)
    answer = hide_page_references(answer)
    return RenderedResult(answer, answer)


def require_qt():
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction, QFont, QKeySequence
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
        "QAction": QAction,
        "QFont": QFont,
        "QKeySequence": QKeySequence,
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
    QAction = qt["QAction"]
    QFont = qt["QFont"]
    QKeySequence = qt["QKeySequence"]
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
            self.build_menu(QAction, QKeySequence, QApplication)

            root = QWidget()
            root.setObjectName("root")
            layout = QVBoxLayout(root)
            layout.setContentsMargins(28, 24, 28, 20)
            layout.setSpacing(14)

            header = QHBoxLayout()
            header.setSpacing(12)
            mark = QLabel("ॐ")
            mark.setObjectName("brandMark")
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_stack = QVBoxLayout()
            title_stack.setSpacing(2)
            title = QLabel("Vishnusahasranamam")
            title.setObjectName("title")
            subtitle = QLabel("Search the nāmas, exact passages, and short questions. Results stay local.")
            subtitle.setObjectName("subtitle")
            title_stack.addWidget(title)
            title_stack.addWidget(subtitle)
            header.addWidget(mark)
            header.addLayout(title_stack, 1)
            layout.addLayout(header)

            search_row = QHBoxLayout()
            search_row.setSpacing(10)
            self.query = QLineEdit()
            self.query.setPlaceholderText("Example: प्राणदः, Madhava, or where do the three Vedas come from")
            self.query.setClearButtonEnabled(True)
            self.query.returnPressed.connect(self.run_search)
            self.find_button = QPushButton("Search")
            self.find_button.setObjectName("primary")
            self.find_button.clicked.connect(self.run_search)
            search_row.addWidget(self.query, 1)
            search_row.addWidget(self.find_button)
            layout.addLayout(search_row)

            mode_row = QHBoxLayout()
            mode_row.setSpacing(16)
            self.mode_group = QButtonGroup(self)
            self.entry_mode = QPushButton("Nāma")
            self.sloka_mode = QPushButton("Śloka")
            self.exact_mode = QPushButton("Exact Text")
            self.answer_mode = QPushButton("Question")
            self.help_button = QPushButton("Help")
            self.mode_group.setExclusive(True)
            for button in (self.entry_mode, self.sloka_mode, self.exact_mode, self.answer_mode):
                button.setCheckable(True)
                button.setObjectName("modeButton")
                self.mode_group.addButton(button)
                mode_row.addWidget(button)
            self.entry_mode.setChecked(True)
            mode_row.addStretch(1)
            self.help_button.clicked.connect(self.show_help)
            mode_row.addWidget(self.help_button)
            layout.addLayout(mode_row)

            self.output = QTextEdit()
            self.output.setAcceptRichText(True)
            self.output.setReadOnly(True)
            self.output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.output.setFont(QFont("Arial Unicode MS", 16))
            layout.addWidget(self.output, 1)

            bottom = QHBoxLayout()
            bottom.setSpacing(10)
            copy_button = QPushButton("Copy")
            self.copy_button = copy_button
            copy_button.clicked.connect(self.copy_output)
            clear_button = QPushButton("Clear")
            clear_button.clicked.connect(self.clear)
            exit_button = QPushButton("Quit")
            exit_button.clicked.connect(QApplication.quit)
            self.status = QLabel("Ready")
            self.status.setObjectName("status")
            self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bottom.addWidget(copy_button)
            bottom.addWidget(clear_button)
            bottom.addWidget(exit_button)
            bottom.addStretch(1)
            bottom.addWidget(self.status)
            layout.addLayout(bottom)

            self.setCentralWidget(root)
            self.setStyleSheet(
                """
                QWidget#root {
                    background: #f3f5f1;
                }
                QLabel#brandMark {
                    background: #203f63;
                    color: #ffffff;
                    border-radius: 10px;
                    min-width: 46px;
                    max-width: 46px;
                    min-height: 46px;
                    max-height: 46px;
                    font-family: "Devanagari Sangam MN";
                    font-size: 24px;
                    font-weight: 700;
                }
                QLabel#title {
                    color: #17212d;
                    font-family: "Avenir Next";
                    font-size: 30px;
                    font-weight: 700;
                }
                QLabel#subtitle, QLabel#status {
                    color: #687383;
                    font-family: "Avenir Next";
                    font-size: 14px;
                }
                QLineEdit {
                    background: #ffffff;
                    color: #17212d;
                    border: 1px solid #c9d0d8;
                    border-radius: 8px;
                    padding: 11px 13px;
                    font-family: "Arial Unicode MS";
                    font-size: 18px;
                    selection-background-color: #b8d7ff;
                }
                QLineEdit:focus {
                    border: 1px solid #275d8e;
                }
                QPushButton {
                    background: #ffffff;
                    color: #213042;
                    border: 1px solid #c6ced8;
                    border-radius: 8px;
                    padding: 9px 15px;
                    font-family: "Avenir Next";
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #eef3f7;
                }
                QPushButton#primary {
                    background: #203f63;
                    color: #ffffff;
                    border: 1px solid #203f63;
                    font-weight: 700;
                    min-width: 92px;
                }
                QPushButton#primary:hover {
                    background: #173352;
                }
                QPushButton#modeButton {
                    color: #344255;
                    background: #ffffff;
                    border: 1px solid #c9d0d8;
                    border-radius: 8px;
                    padding: 8px 14px;
                    font-family: "Avenir Next";
                    font-size: 14px;
                    min-width: 78px;
                }
                QPushButton#modeButton:checked {
                    background: #dbe8f3;
                    border: 1px solid #90abc8;
                    color: #173352;
                    font-weight: 700;
                }
                QTextEdit {
                    background: #ffffff;
                    color: #18222f;
                    border: 1px solid #d4d9de;
                    border-radius: 10px;
                    padding: 18px;
                    selection-background-color: #b8d7ff;
                    line-height: 145%;
                }
                """
            )

        def build_menu(self, QAction, QKeySequence, QApplication) -> None:
            self.file_menu = self.menuBar().addMenu("File")
            self.exit_action = QAction("Exit", self)
            self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
            self.exit_action.triggered.connect(QApplication.quit)
            self.file_menu.addAction(self.exit_action)

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
                elif self.sloka_mode.isChecked():
                    result = render_sloka(query)
                elif self.exact_mode.isChecked():
                    result = render_sloka(query) if re.fullmatch(r"\s*[0-9०-९]{1,3}\s*", query) else render_exact(query)
                else:
                    result = render_answer(query)
            except Exception as exc:  # pragma: no cover - UI safety net
                result = RenderedResult(f"Error: {exc}", "")
            self.output.setHtml(display_text_to_html(result.display_text))
            self.output.verticalScrollBar().setValue(0)
            self.copy_text = result.copy_text
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
