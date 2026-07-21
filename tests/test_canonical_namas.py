from vishnu_retrieval.canonical import canonical_by_number, load_canonical_namas
from vishnu_retrieval.search import canonical_numbers_for_query
import re


def test_canonical_table_has_all_1000_namas():
    rows = load_canonical_namas()

    assert len(rows) == 1000
    assert [int(row["number"]) for row in rows] == list(range(1, 1001))


def test_canonical_devanagari_labels_are_sanskrit_only():
    rows = load_canonical_namas()

    for row in rows:
        devanagari = row["devanagari"]
        assert devanagari.strip()
        assert re.search(r"[\u0900-\u097F]", devanagari)
        assert not re.search(r"[A-Za-z]", devanagari)


def test_common_roman_spellings_find_hrisikesa():
    assert canonical_numbers_for_query("Hrisikesa") == [47]
    assert canonical_numbers_for_query("Hrishikesa") == [47]


def test_close_roman_names_do_not_merge():
    assert canonical_numbers_for_query("Madhava") == [72, 167, 735]
    assert canonical_numbers_for_query("Medhavi") == [77]


def test_known_endpoints_are_clean():
    assert canonical_by_number(1)["roman"] == "viśvam"
    assert canonical_by_number(1000)["roman"] == "sarvapraharaṇāyudhaḥ"
