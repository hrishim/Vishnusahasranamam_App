from __future__ import annotations

import json
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path

from vishnu_retrieval.io import DERIVATION_OVERRIDES_JSON
from vishnu_retrieval.canonical import devanagari_to_iast, load_canonical_namas
from vishnu_retrieval.corrections import apply_curated_corrections
from vishnu_retrieval.search import roman_match_key


SOURCE_DOCX = Path("outputs/pdf_ocr_studio_sources/Vishnusahasranamam_PDF_OCR_Studio_corrected_vol_01_05.docx")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
LATIN_RE = re.compile(r"[A-Za-z]")


STOP_WORD_RE = re.compile(
    r"\b(?:The|One|He|She|It|This|That|Who|Which|Because|Since|When|Where|What|A|An)\b",
    re.IGNORECASE,
)


def candidate_key(line: str) -> str:
    latin_part = re.sub(r"[\u0900-\u097F।॥|]+", " ", line)
    latin_part = re.sub(r"\([^)]*\)", " ", latin_part)
    return roman_match_key(latin_part)


def heading_candidate_key(line: str) -> str:
    latin_part = re.sub(r"[\u0900-\u097F।॥|]+", " ", line)
    latin_part = re.sub(r"\([^)]*\)", " ", latin_part).strip()
    latin_part = re.split(r"[.;:।॥|]", latin_part, maxsplit=1)[0].strip()
    stop = STOP_WORD_RE.search(latin_part)
    if stop and stop.start() > 0:
        latin_part = latin_part[: stop.start()]
    latin_part = re.sub(r"\b(?:The|One|He|This|That).*$", "", latin_part).strip()
    return roman_match_key(latin_part)


def canonical_key_for_heading(line: str, aliases: list[tuple[str, set[str]]]) -> str:
    full_key = candidate_key(line)
    short_key = heading_candidate_key(line)
    for key, alias_keys in aliases:
        if any(alias and (alias in full_key or alias in short_key or full_key.startswith(alias)) for alias in alias_keys):
            return key
    best_key = ""
    best_score = 0.0
    probe = short_key or full_key[:32]
    if not probe:
        return ""
    for key, alias_keys in aliases:
        for alias in alias_keys:
            if not alias:
                continue
            score = SequenceMatcher(None, probe[: max(len(alias), len(probe))], alias).ratio()
            if score > best_score:
                best_score = score
                best_key = key
    return best_key if best_score >= 0.78 else ""


def is_derivation_line(line: str) -> bool:
    if not DEVANAGARI_RE.search(line) or LATIN_RE.search(line):
        return False
    if "।।" in line or "||" in line:
        return False
    if len(DEVANAGARI_RE.findall(line)) < 8:
        return False
    markers = (
        "इति",
        "अस्य",
        "यस्य",
        "येन",
        "यस्मात्",
        "यस्मिन्",
        "त्वात्",
        "रूपेण",
        "नास्ति",
        "विद्यते",
        "करोति",
        "भवति",
        "वहन्",
        "लभ्यते",
        "जायते",
        "धत्ते",
        "गच्छति",
    )
    return any(marker in line for marker in markers)


def dev_key(text: str) -> str:
    return re.sub(r"[^\u0900-\u097F]", "", text).replace(":", "ः")


def derivation_name_match(line: str, name: str, roman: str = "") -> bool:
    name_key = dev_key(name).rstrip("ः")
    target_roman = roman_match_key(roman or devanagari_to_iast(name))
    line_roman = roman_match_key(devanagari_to_iast(line))
    if len(target_roman) >= 5 and target_roman in line_roman:
        return True
    if len(name_key) < 4:
        return False
    line_key = dev_key(line).rstrip("ः")
    if name_key not in line_key:
        return False
    if f"इति {name_key}" in line_key or f"इति{name_key}" in line_key:
        return True
    if re.search(re.escape(name_key) + r"[ःम्]*[।|]?\s*$", line_key):
        return True
    return any(marker in line for marker in ("अस्येति", "यस्येति", "त्वात्", "न विद्यते", "रूपेण"))


def join_derivation_continuation(lines: list[str], index: int) -> str:
    parts = [lines[index]]
    for probe in range(index + 1, min(index + 3, len(lines))):
        candidate = lines[probe]
        if not is_derivation_line(candidate):
            break
        if len(" ".join(parts)) > 220:
            break
        if parts[-1].endswith(("।", "|")) and not candidate.startswith(("भवति", "न ", "वा ", "इति", "उच्यते", "वाचकः")):
            break
        parts.append(candidate)
    return " ".join(parts)


def main() -> int:
    if not SOURCE_DOCX.exists():
        raise SystemExit(f"Missing source docx: {SOURCE_DOCX}")
    text = subprocess.check_output(["textutil", "-convert", "txt", "-stdout", str(SOURCE_DOCX)], text=True)
    text = apply_curated_corrections(text)
    lines = [line.strip() for line in text.replace("\u2028", "\n").replace("\f", "\n").splitlines()]
    aliases: list[tuple[str, set[str]]] = []
    for row in load_canonical_namas():
        key = roman_match_key(str(row.get("roman", "")))
        alias_keys = {
            key,
            roman_match_key(str(row.get("source_title", ""))),
        }
        aliases.append((key, {alias for alias in alias_keys if alias}))

    overrides: dict[str, str] = {}
    for index, line in enumerate(lines[:-2]):
        if not DEVANAGARI_RE.search(line) or not LATIN_RE.search(line):
            continue
        if any(mark in line for mark in ("।।", "||", "BG.", "Up.")):
            continue
        keys = {candidate_key(line), canonical_key_for_heading(line, aliases)}
        keys = {key for key in keys if key}
        if not keys:
            continue
        for candidate in lines[index + 1 : index + 5]:
            if DEVANAGARI_RE.search(candidate) and len(DEVANAGARI_RE.findall(candidate)) >= 8 and not LATIN_RE.search(candidate):
                for key in keys:
                    overrides.setdefault(key, candidate)
                break

    for row in load_canonical_namas():
        key = roman_match_key(str(row.get("roman", "")))
        name = str(row.get("devanagari", ""))
        roman = str(row.get("roman", ""))
        if not key or key in overrides or not name:
            continue
        for index, line in enumerate(lines):
            if not is_derivation_line(line):
                continue
            if not derivation_name_match(line, name, roman):
                continue
            overrides[key] = join_derivation_continuation(lines, index)
            break

    canonical_aliases: list[tuple[str, set[str]]] = []
    for row in load_canonical_namas():
        key = roman_match_key(str(row.get("roman", "")))
        alias_keys = {
            key,
            roman_match_key(str(row.get("source_title", ""))),
        }
        canonical_aliases.append((key, {alias for alias in alias_keys if alias}))

    for found_key, value in list(overrides.items()):
        if any(found_key == key for key, _ in canonical_aliases):
            continue
        best_key = ""
        best_score = 0.0
        for key, alias_keys in canonical_aliases:
            for alias in alias_keys:
                if not alias:
                    continue
                score = SequenceMatcher(None, found_key, alias).ratio()
                if score > best_score:
                    best_score = score
                    best_key = key
        if best_key and best_score >= 0.90:
            overrides.setdefault(best_key, value)

    manual = {
        "durlabha": "दुःखेन, (दुर्लभया भक्त्या) लभ्यत इति दुर्लभः।",
        "ijya": "यष्टव्योऽपि अयमेवेति इज्यः।",
        "punarvasu": "पुनः पुनः शरीरेषु वसति क्षेत्रज्ञरूपेणेति पुनर्वसुः।",
        "nara": "न रीयते इति नरः।",
        "vivikta": "इत्थं वर्धमानोऽपि पृथगेव तिष्ठतीति विविक्तः।",
        "pratapana": "सवित्रादिविभूतिभिः विश्वं प्रतापयतीति प्रतापनः।",
        "mahasana": "कल्पान्ते सर्वग्रसनात् महदशनमस्येति महाशनः।",
        "apramatta": "अधिकारिभ्यः कर्मानुरूपं फलं प्रयच्छन् न प्रमाद्यतीति अप्रमत्तः।",
        "padmanibheksana": "पद्मनिभे ईक्षणे अस्येति पद्मनिभेक्षणः।",
        "vikarta": "विचित्रं भुवनं कृतवान् इति विकर्ता।",
        "dhruva": "अविनाशित्वात् ध्रुवः।",
        "dhanesvara": "धनानां ईशः धनेश्वरः।",
        "somapa": "सोमं पिबति सर्वयज्ञेषु यष्टव्यदेवतारूपेण इति सोमपः।",
        "amrtapa": "स्वात्मामरतरसं पिबन् अमृतपः।",
        "antaka": "अन्तं करोति भूतानामिति अन्तकः।",
        "maharha": "मह्यः पूजा तदर्हत्वात् महार्हः।",
        "kanakangadi": "कनकमयानि अङ्गानि अस्येति कनकाङ्गदी।",
        "guhya": "रहस्योपनिषद्-वेद्यत्वात् गुहायां हृदयाकाशे निहित इति वा गुह्यः।",
        "sarvadrgvyasa": "सर्वदृक् च असौ व्यासश्च इति सर्वदृग्व्यासः।",
        "shrisa": "श्रियः ईशः श्रीशः।",
        "jyotirganesvara": "ज्योतिर्गणानां ईश्वरः ज्योतिर्गणेश्वरः।",
        "vijitatma": "विजितः आत्मा मनः येन सः विजितात्मा।",
        "dhananjaya": "प्रभूतं धनमजयत् तेन धनञ्जयः।",
        "brahmanya": "तपो वेदाश्च विप्राश्च ज्ञानं च ब्रह्मसंज्ञितम्। तेभ्यो हितत्वात् ब्रह्मण्यः।",
        "sannivasa": "सतां विदुषामाश्रयः सन्निवासः।",
        "anekamurti": "अवतारेषु स्वेच्छया रूपाणि भजत इति अनेकमूर्तिः।",
        "vyagra": "विगतम् अग्रम् अन्तो विनाशोऽस्येति व्यग्रः।",
        "sulabha": "भक्तेभ्यः सुलभः।",
        "tattvam": "तत्त्वम् अमृतं सत्यं परमार्थसतत्त्वम् इत्येते एकार्थवाचिनः।",
        "ekatma": "एकश्चासौ आत्मा चेति एकात्मा।",
        "janmamrtyujaratiga": "षड्भावविकारान् अतीत्य गच्छतीति जन्ममृत्युजरातिगः।",
        "atmavan": "आत्मा अस्यास्तीति आत्मवान्।",
        "janardana": "जनान् अर्दयति इति जनार्दनः। जनैः अर्द्यते याच्यते इति वा जनार्दनः।",
        "padmi": "पद्मं अस्य अस्ति इति पद्मी।",
        "guha": "गुहते संवृणोति स्वरूपादि निजमाययेति गुहः।",
        "paramaspasta": "संविदात्मतया स्पष्टः परमस्पष्टः।",
        "pusta": "पुष्णाति इति पुष्टः।",
        "virata": "विगतं रतमस्य विषयसेवायामिति विरतः।",
        "naksatranemi": "नक्षत्राणां नेमिः केन्द्रम् इति नक्षत्रनेमिः।",
        "subrata": "सु शोभनं व्रतमस्येति सुव्रतः।",
        "mahayajva": "महांश्चासौ यज्वा चेति महायज्वा।",
        "tat": "तनोतीति ब्रह्म तत्।",
        "varanga": "वराणि अङ्गानि अस्येति वराङ्गः।",
        "visama": "न विद्यते समो यस्य सः विषमः।",
        "cala": "चरतीति चलः।",
        "caturvedavit": "चतुरो वेदान् वेत्तीति चतुर्वेदवित्।",
        "samavarta": "संसारचक्रस्य सम्यगावर्तक इति समावर्तः।",
        "anu": "सौक्ष्म्यातिशयशालित्वात् अणुः।",
        "krsa": "कृशत्वात् कृशः।",
        "svadhrta": "स्वेनैव धृतः स्वधृतः।",
        "priyarha": "प्रियं अर्हतीति प्रियार्हः।",
        "yajva": "यजतीति यज्वा।",
        "svayamjata": "निमित्तकारणमपि स एवेति दर्शयितुं स्वयंजातः।",
    }
    overrides.update(manual)
    payload = {
        "schema_version": 1,
        "source": str(SOURCE_DOCX),
        "count": len(overrides),
        "overrides": dict(sorted(overrides.items())),
    }
    DERIVATION_OVERRIDES_JSON.parent.mkdir(parents=True, exist_ok=True)
    DERIVATION_OVERRIDES_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(DERIVATION_OVERRIDES_JSON)
    print(f"overrides={len(overrides)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
