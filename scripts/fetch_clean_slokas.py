from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "index" / "slokas.json"
URLS = [
    "https://www.swami-krishnananda.org/vishnu/vishnu_1.html",
    "https://www.swami-krishnananda.org/vishnu/vishnu_2.html",
    "https://www.swami-krishnananda.org/vishnu/vishnu_3.html",
]


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")


def page_text(url: str) -> str:
    html = urlopen(url, timeout=30).read().decode("utf-8", "replace")
    parser = TextParser()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def extract_slokas(url: str) -> list[dict]:
    text = page_text(url)
    pattern = re.compile(
        r"(?P<dev>(?:[^\n]*[\u0900-\u097F][^\n]*\n){1,3})\s*"
        r"(?P<roman>(?:[^\n]*[A-Za-zāīūṛṝḷṅñṭḍṇśṣḥĀĪŪṚṜḶṄÑṬḌṆŚṢḤ][^\n]*\n?){1,3}?"
        r"\(\s*(?P<num>\d{1,3})\s*\))"
    )
    slokas: list[dict] = []
    for match in pattern.finditer(text):
        devanagari = match.group("dev").strip()
        roman = match.group("roman").strip()
        number = int(match.group("num"))
        if not 1 <= number <= 108:
            continue
        if "॥" not in devanagari:
            continue
        slokas.append(
            {
                "number": number,
                "devanagari": devanagari,
                "roman": roman,
                "text": f"{devanagari}\n\n{roman}",
                "source_url": url,
            }
        )
    return slokas


def main() -> int:
    by_number: dict[int, dict] = {}
    for url in URLS:
        for sloka in extract_slokas(url):
            by_number[sloka["number"]] = sloka
    missing = [number for number in range(1, 109) if number not in by_number]
    if missing:
        raise SystemExit(f"Missing sloka numbers: {missing}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "source": "Swami Krishnananda - Sri Vishnu Sahasranama Stotram",
        "source_urls": URLS,
        "slokas": [by_number[number] for number in range(1, 109)],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['slokas'])} clean slokas -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
