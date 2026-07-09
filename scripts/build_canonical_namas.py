from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from vishnu_retrieval.canonical import devanagari_key, devanagari_to_iast


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "index" / "canonical_namas.json"
AUDIT = ROOT / "outputs" / "clean_doc_check" / "all_namas_audit.md"
PDF_INDEX = Path(
    "/Users/sathyavasu/Library/CloudStorage/OneDrive-Personal/HrishiProton/MyDataShare/Books/Philosophy/Vishnusahasranamam/VS Swamiji/VS_Index.pdf"
)
PDF_OCR = ROOT / "tmp" / "pdfs" / "vs_index" / "VS_Index_ocr.txt"
DOCX_INDEX = Path("/Users/sathyavasu/Downloads/VS_IndexSer.docx")

MANUAL_DEVANAGARI = {
    6: "भूतभृत्",
    18: "योगः",
    34: "प्रभवः",
    35: "प्रभुः",
    47: "हृषीकेशः",
    60: "प्रभूतः",
    63: "मङ्गलं परम्",
    65: "प्राणदः",
    104: "वसुः",
    120: "शाश्वतस्थाणुः",
    124: "सर्वविद्भानुः",
    139: "चतुर्दंष्ट्रः",
    150: "पुनर्वसुः",
    153: "प्रांशुः",
    156: "ऊर्जितः",
    162: "यमः",
    170: "महामायः",
    177: "अनिर्देश्यवपुः",
    199: "सर्वदृक्",
    216: "स्रग्वी",
    220: "श्रीमान्",
    233: "वह्निः",
    244: "जह्नुः",
    237: "प्रसन्नात्मा",
    247: "असङ्ख्येयः",
    253: "सिद्धसङ्कल्पः",
    270: "वसुः",
    274: "प्रकाशनः",
    276: "प्रकाशात्मा",
    287: "औषधम्",
    299: "प्रभुः",
    301: "युगावर्तः",
    321: "प्राणदः",
    350: "महर्द्धिः",
    345: "पद्मनिभेक्षणः",
    366: "हेतुः",
    408: "प्राणदः",
    412: "शत्रुघ्नः",
    415: "अधोक्षजः",
    428: "प्रमाणम्",
    441: "नक्षत्री",
    451: "सर्वदर्शी",
    460: "सुहृत्",
    470: "वत्सरः",
    473: "रत्नगर्भः",
    469: "नैककर्मकृत्",
    489: "भूतमहेश्वरः",
    507: "पुरुषोत्तमः",
    515: "मुकुन्दः",
    523: "स्वाभाव्यः",
    525: "प्रमोदनः",
    529: "सत्यधर्मा",
    531: "महर्षिः कपिलाचार्यः",
    538: "महावराहः",
    551: "दृढः",
    557: "महामनाः",
    562: "हलायुधः",
    571: "दिवःस्पृक्",
    572: "सर्वदृग्व्यासः",
    588: "स्रष्टा",
    590: "कुवलेशयः",
    596: "अनिवर्ती",
    598: "सङ्क्षेप्ता",
    613: "श्रीमान्",
    615: "स्वक्षः",
    619: "ज्योतिर्गणेश्वरः",
    622: "सत्कीर्तिः",
    633: "अर्चिष्मान्",
    634: "अर्चितः",
    640: "प्रद्युम्नः",
    656: "अनिर्देश्यवपुः",
    674: "महोरगः",
    676: "महायज्वा",
    688: "पुण्यकीर्तिः",
    696: "वसुः",
    698: "हविः",
    705: "यदुश्रेष्ठः",
    706: "सन्निवासः",
    714: "दृप्तः",
    718: "महामूर्तिः",
    719: "दीप्तमूर्तिः",
    721: "अनेकमूर्तिः",
    723: "शतमूर्तिः",
    730: "यत्",
    737: "सुवर्णवर्णः",
    744: "घृताशीः",
    748: "मानदः",
    749: "मान्यः",
    750: "लोकस्वामी",
    753: "मेधजः",
    759: "सर्वशस्त्रभृतां वरः",
    772: "एकपात्",
    770: "चतुर्भावः",
    793: "रत्ननाभः",
    797: "शृङ्गी",
    802: "सर्वयोगीश्वरेश्वरः",
    803: "महाह्रदः",
    805: "महाभूतः",
    825: "चाणूरान्ध्रनिषूदनः",
    826: "सहस्रार्चिः",
    827: "सप्तजिह्वः",
    838: "स्थूलः",
    839: "गुणभृत्",
    841: "महान्",
    848: "कथितः",
    868: "सात्त्विकः",
    872: "प्रियार्हः",
    846: "वंशवर्धनः",
    879: "हुतभुक्",
    887: "हुतभुक्",
    893: "सदामर्षी",
    894: "लोकाधिष्ठानम्",
    910: "ऊर्जितशासनः",
    920: "विद्वत्तमः",
    926: "दुःस्वप्ननाशनः",
    963: "तत्त्वम्",
    964: "तत्त्ववित्",
    965: "एकात्मा",
    966: "जन्ममृत्युजरातिगः",
    956: "प्राणदः",
    959: "प्रमाणम्",
    960: "प्राणनिलयः",
    962: "प्राणजीवनः",
    973: "यज्वा",
    986: "स्वयंजातः",
    990: "स्रष्टा",
    996: "शार्ङ्गधन्वा",
}

MANUAL_SOURCE_TITLES = {
    580: "Sannyāsakṛt",
    797: "Śṛṅgī",
    908: "Cakrī",
    995: "Cakrī",
}


def ensure_pdf_ocr() -> str:
    if PDF_OCR.exists():
        return PDF_OCR.read_text(encoding="utf-8")
    render_dir = ROOT / "tmp" / "pdfs" / "vs_index" / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", "300", str(PDF_INDEX), str(render_dir / "page300")],
        check=True,
    )
    text_parts: list[str] = []
    for image in sorted(render_dir.glob("page300-*.png")):
        out_base = ROOT / "tmp" / "pdfs" / "vs_index" / f"ocr_{image.stem}"
        subprocess.run(
            ["tesseract", str(image), str(out_base), "-l", "san+hin+eng", "--psm", "6"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        text_parts.append(out_base.with_suffix(".txt").read_text(encoding="utf-8"))
    PDF_OCR.write_text("\n".join(text_parts), encoding="utf-8")
    return PDF_OCR.read_text(encoding="utf-8")


def docx_text() -> str:
    if not DOCX_INDEX.exists():
        return ""
    try:
        from docx import Document
    except Exception:
        return ""
    return "\n".join(p.text for p in Document(DOCX_INDEX).paragraphs)


def split_segments(line: str) -> list[str]:
    parts = re.split(r"\s*\|\s*", line)
    if len(parts) > 1:
        return parts
    return [line]


def candidate_name(segment: str) -> str:
    text = segment.strip().strip("()[]{}")
    text = re.sub(r"[A-Za-z=_.]+", " ", text)
    text = re.sub(r"[^\u0900-\u097F\s:;ऽ्\u200c\u200d-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(" -").replace(":", "ः").replace("\u200c", "").replace("\u200d", "")


def index_candidates(text: str) -> dict[int, list[str]]:
    candidates: dict[int, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if not re.search(r"[\u0900-\u097F]", line):
            continue
        for segment in split_segments(line):
            numbers = [
                int(value)
                for value in re.findall(r"(?<!\d)(\d{1,4})(?!\d)", segment)
                if 1 <= int(value) <= 1000
            ]
            if not numbers:
                continue
            before_first_number = re.split(r"(?<!\d)\d{1,4}(?!\d)", segment, maxsplit=1)[0]
            name = candidate_name(before_first_number)
            if not name:
                continue
            for number in numbers:
                candidates[number].append(name)
    return candidates


def audit_titles() -> dict[int, dict]:
    if not AUDIT.exists():
        return {}
    rows: dict[int, dict] = {}
    pattern = re.compile(r"^\|\s*(\d{1,4})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$")
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        number = int(match.group(1))
        raw_num = match.group(2).strip()
        page = match.group(3).strip()
        title = match.group(4).replace("\\|", "|").strip()
        if not (1 <= number <= 1000) or title == "MISSING":
            continue
        rows[number] = {
            "source_raw_number": None if raw_num in {"", "None"} else raw_num,
            "page": int(page) if page.isdigit() else None,
            "source_title": title,
        }
    return rows


def roman_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ṁ", "m").replace("ṃ", "m")
    text = text.replace("ś", "s").replace("ṣ", "s")
    return re.sub(r"[^a-z]", "", text)


def choose_name(number: int, names: list[str], source_title: str = "") -> str:
    if number in MANUAL_DEVANAGARI:
        return MANUAL_DEVANAGARI[number].replace(":", "ः")
    cleaned = [name for name in names if devanagari_key(name)]
    if not cleaned:
        return ""
    counts = Counter(cleaned)
    source_key = roman_key(source_title)

    def score(item: tuple[str, int]) -> tuple[float, int, int, str]:
        name, count = item
        candidate_key = roman_key(devanagari_to_iast(name))
        similarity = SequenceMatcher(None, source_key, candidate_key).ratio() if source_key and candidate_key else 0
        return (similarity, count, len(candidate_key), name)

    return sorted(counts.items(), key=score, reverse=True)[0][0]


def main() -> int:
    pdf_candidates = index_candidates(ensure_pdf_ocr())
    docx_candidates = index_candidates(docx_text())
    audit = audit_titles()
    namas: list[dict] = []
    missing_names: list[int] = []
    for number in range(1, 1001):
        names: list[str] = []
        names.extend(pdf_candidates.get(number, []))
        names.extend(docx_candidates.get(number, []))
        source_title = MANUAL_SOURCE_TITLES.get(number, audit.get(number, {}).get("source_title", ""))
        devanagari = choose_name(number, names, source_title)
        if not devanagari:
            missing_names.append(number)
        row = {
            "number": number,
            "devanagari": devanagari,
            "key": devanagari_key(devanagari),
            "roman": devanagari_to_iast(devanagari) if devanagari else "",
            "source_title": source_title,
            "source_page": audit.get(number, {}).get("page"),
            "index_candidates": sorted(set(names))[:8],
        }
        namas.append(row)

    payload = {
        "schema_version": 1,
        "source_policy": "Teaching text remains the explanation source; this file is only a name-number matching aid.",
        "count": len(namas),
        "missing_devanagari_numbers": missing_names,
        "namas": namas,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)
    print(f"count={len(namas)} missing_devanagari={len(missing_names)}")
    if missing_names:
        print("missing:", missing_names)
    return 0 if len(namas) == 1000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
