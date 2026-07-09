from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.desktop_app import entry_body_with_clean_heading
from vishnu_retrieval.search import extract_entry_by_number


OUT = Path("outputs/clean_doc_check/rendered_text_defects_audit.md")


DEFECT_PATTERNS = {
    r"\bLordkin\b": "broken 'Lord in'",
    r"\bhowkit\b": "broken 'how it'",
    r"\bofcourse\b": "missing space in 'of course'",
    r"\binspite\b": "missing space in 'in spite'",
    r"\bac\s+uiring\b": "broken 'acquiring'",
    r"\bP+Paramātmā\b": "extra P in Paramātmā",
    r"\bpPParamātmā\b": "extra P in Paramātmā",
    r"\blo\s+as\b": "broken 'lokas'",
    r"\bśa\s+tis\b": "broken 'śaktis'",
    r"\bī\s+ṣaṇe\b": "broken 'īkṣaṇe'",
    r"\badmī\b": "missing P in Padmī",
    r"\bratāpana\b": "missing P in Pratāpana",
    r"\bhanavān\b": "missing D in Dhanavān",
    r"\bvara-arpana\b": "missing Īś in Īśvara-arpana",
    r"\bvara ārādhana\b": "missing Īś in Īśvara-ārādhana",
    r"\b(?:^|[^A-Za-zāīūṛṝḷṅñṭḍṇśṣḥ])arma\b": "missing k in karma",
    r"\b(?:^|[^A-Za-zāīūṛṝḷṅñṭḍṇśṣḥ])armas\b": "missing k in karmas",
    r"\bujya Swamiji\b": "missing P in Pujya Swamiji",
    r"\bmaange more’so\b": "missing space after quote",
    r"\bneeds\s+to\s+done\b": "missing be",
    r"\bBrahmanand\b": "missing space in Brahman and",
    r"\bupto\b": "missing space in up to",
    r"\barriv(?:e|es|ed|ing)\s+atka\b": "broken 'at a'",
    r"\batka\s+\w+": "broken 'at a'",
    r"\b[A-Za-z]+k(?:you|years)\b": "glued k before English word",
    r"\bqqquiet\w*\b": "repeated q OCR error",
    r"\bdddon[’']t\b": "repeated d OCR error",
    r"\bthinkk+\w*\b": "repeated k OCR error",
    r"\bexceeed\b": "repeated e OCR error",
    r"\batttibute\b": "repeated t OCR error",
    r"\bviśvaand\b": "missing space after viśva",
    r"\bincludeskyour\b": "glued 'includes your'",
    r"\bbecomeskyour\b": "glued 'becomes your'",
    r"\bexpresskyour\b": "glued 'express your'",
    r"\bblesskyourself\b": "glued 'bless yourself'",
    r"\bvariousky(?:ugas|ajñas)\b": "glued 'various'",
    r"\bcomaparison\b": "misspelled comparison",
    r"\bcharactersitcs\b": "misspelled characteristics",
    r"\bcontinous\b": "misspelled continuous",
    r"\bFaceboo\b|\bFacebookk+\b": "damaged Facebook",
    r"\bfaceboo\b|\bfacebookk+\b": "damaged Facebook",
    r"\bMiMilky\b": "damaged Milky",
    r"\bmimilky\b": "damaged milky",
    r"\bD+D(?:aśaratha|haneśvara|evahūti)\b": "repeated initial D",
    r"\bbabacked\b": "damaged backed",
    r"\bq+qualified\b": "damaged qualified",
    r"\bk+knowingly\b": "damaged knowingly",
    r"\bunk+knowingly\b": "damaged unknowingly",
    r"\bvara\s+ārādhana\b": "missing Īśvara in Īśvara-ārādhana",
    r"\bĪś(?:Īś)+vara\b": "repeated Īś in Īśvara",
    r"\bś+ś(?:rutis|raddhā)\b": "repeated ś",
    r"\bma\s+ingPātala\b": "damaged making Pātāla",
    r"\bsna\s+es\b": "damaged snakes",
    r"\bnamask\s+ra\b": "damaged namaskāra",
    r"\bsatyasa\s+alpa\b": "damaged satyasaṅkalpa",
    r"\bupala\s+ṣaṇa\b": "damaged upalakṣaṇa",
    r"\bkarma\s+ānda\b": "damaged karma-kāṇḍa",
    r"\bsvayam-pra\s+āśa\b": "damaged svayam-prakāśa",
    r"\bdevotes\. arigraha\b": "damaged devotees/Parigraha",
    r"\bGuru urnima\b": "damaged Guru Pūrṇimā",
    r"\baśaratha\b": "damaged Daśaratha",
    r"\bPP+rahlāda\b": "damaged Prahlāda",
    r"\bDD+evadutta\b": "damaged Devadutta",
    r"\bAgni,the\b": "missing space after comma",
    r"\bdevotes\.\s*arigraha\b": "damaged devotees/Parigraha sentence",
    r"\bhance he is called\b": "damaged hence He",
    r"\bpuṇyaśravaṇa\s+rtana\b": "damaged puṇyaśravaṇa-kīrtana",
    r"\bK\s+rtana\b": "damaged Kīrtana",
    r"\brtana,\s+singing\b": "damaged kīrtana",
    r"\brtana\.\s+Īśvara\b": "damaged kīrtana",
    r"\bVāsudevaas\b": "missing space after Vāsudeva",
    r"\bisVāsudeva\b": "missing space before Vāsudeva",
    r"\bthekṣetra\b": "missing space before kṣetra",
    r"\bphilosoper\b": "misspelled philosopher",
    r"\bself-\s+consciousness\b": "broken self-consciousness",
    r"\bself-\s+judgement\b": "broken self-judgement",
    r"\bself loath\b": "damaged self-loathing",
    r"\bknowledge-\s+wise\b": "broken knowledge-wise",
}


@dataclass
class Defect:
    number: int
    pattern: str
    reason: str
    context: str


def context(text: str, start: int, end: int) -> str:
    return text[max(0, start - 90) : min(len(text), end + 140)].replace("\n", " ").replace("|", "/")


def main() -> int:
    defects: list[Defect] = []
    for row in load_canonical_namas():
        number = int(row["number"])
        hits = extract_entry_by_number(number, window_after=5)
        if not hits:
            defects.append(Defect(number, "missing-entry", "No rendered entry.", ""))
            continue
        text = entry_body_with_clean_heading(hits[0])
        for pattern, reason in DEFECT_PATTERNS.items():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                defects.append(Defect(number, pattern, reason, context(text, match.start(), match.end())))

    lines = [
        "# Rendered Text Defect Audit",
        "",
        f"Entries checked: {len(load_canonical_namas())}",
        f"Defects found: {len(defects)}",
        "",
        "| Entry | Reason | Pattern | Context |",
        "|---:|---|---|---|",
    ]
    for defect in defects[:500]:
        lines.append(
            f"| {defect.number} | {defect.reason} | `{defect.pattern}` | {defect.context} |"
        )
    if len(defects) > 500:
        lines.append(f"|  | ... {len(defects) - 500} more |  |  |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(f"defects={len(defects)}")
    return 1 if defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
