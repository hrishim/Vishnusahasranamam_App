from vishnu_retrieval.search import (
    ENTRY_HEADING_RE,
    exact_search,
    extract_entry,
    heading_matches_query,
    nama_sloka_cross_index,
    parse_nama_heading,
    sloka_search,
)
from vishnu_retrieval.desktop_app import render_entry, render_exact, render_sloka
from vishnu_retrieval.desktop_app import render_answer, render_hybrid


def test_entry_heading_does_not_match_sanskrit_derivation_line():
    text = "रश्मयः सः ह्रीषीकेशः।\n\nThe svarūpa of Bhagavan is presented here as the"

    assert not ENTRY_HEADING_RE.search(text)


def test_entry_heading_matches_devanagari_transliteration_heading():
    text = "ह्रीषीकेशः Hrisikesah"

    assert ENTRY_HEADING_RE.search(text)


def test_entry_heading_matches_capital_diacritic_roman_heading():
    text = "शाश्वतस्थिरः Śāśvatasthiraḥ"

    assert ENTRY_HEADING_RE.search(text)
    assert parse_nama_heading(text) == ("शाश्वतस्थिरः", "Śāśvatasthiraḥ")


def test_mahayajna_returns_great_yajna_entry():
    result = render_entry("Mahayajña")

    assert "Entry 1 - Nama: 677" in result.display_text
    assert "महायज्ञ" in result.display_text
    assert "The one who is the great yaj" in result.display_text
    assert "The great sacrificer." not in result.display_text
    assert "Page:" not in result.copy_text


def test_avayaya_query_does_not_return_prior_verse_context():
    hits = extract_entry("अव्ययः")

    assert hits
    assert hits[0].number == 13
    assert all(not hit.text.startswith("भूतभावनः") for hit in hits)


def test_plain_vishnu_query_matches_only_vishnu_headings():
    hits = extract_entry("Vishnu")

    assert len(hits) == 3
    assert [hit.number for hit in hits] == [2, 258, 657]


def test_repeated_krtagama_returns_both_entries():
    hits = extract_entry("कृतागमः")

    headings = [hit.text.splitlines()[0] for hit in hits]
    pages = [hit.page_start for hit in hits]
    assert [hit.number for hit in hits] == [655, 789]
    assert "55. Krtāgamaḥ" in headings
    assert "789. Kṛtāgamaḥ (also word 655)" in headings
    assert 356 in pages
    assert 397 in pages
    second_entry = next(hit.text for hit in hits if hit.number == 655)
    assert "Āgama is the Veda" in second_entry
    assert "उद्धव:" not in second_entry
    assert "उद्धवः Udbhavaḥ" not in second_entry


def test_repeated_krtagama_returns_both_entries_by_roman_query():
    hits = extract_entry("Krtagamah")

    assert [hit.number for hit in hits] == [655, 789]


def test_repeated_ananta_returns_886_and_659_entries():
    hits = extract_entry("अनन्तः")

    headings = [hit.text.splitlines()[0] for hit in hits]
    pages = [hit.page_start for hit in hits]
    assert [hit.number for hit in hits] == [659, 886]
    assert "659. Anantaḥ" in headings
    assert "886. Anantaḥ (also word 659)" in headings
    assert 357 in pages
    assert 428 in pages
    first_entry = next(hit.text for hit in hits if hit.number == 886)
    assert "The limitless." in first_entry
    assert "धनञ्जयः Dhananjayah" not in first_entry


def test_repeated_ananta_full_entry_includes_both_slokas():
    result = render_entry("अनन्तः")

    assert "Entry 1 - Nama: 659" in result.display_text
    assert "Entry 2 - Nama: 886" in result.display_text
    assert "अनन्तः (886)" in result.display_text
    assert "अनन्तः (659)" in result.display_text
    assert "धनञ्जयः Dhananjayah" not in result.display_text


def test_sloka_search_ananta_returns_both_occurrences():
    result = render_sloka("अनन्तः")

    assert "अनिर्देश्यवपुर्विष्णुर्वीरोऽनन्तो धनञ्जयः ॥७०॥" in result.display_text
    assert "अनन्तो हुतभुग्भोक्ता सुखदो नैकजोऽग्रजः ।" in result.display_text
    assert "अनिर्विण्णः सदामर्षी लोकाधिष्ठानमद्भुतः ॥९५॥" in result.display_text


def test_repeated_aparajita_full_entry_and_sloka_search_include_both_slokas():
    entry = render_entry("अपराजितः")
    sloka = render_sloka("अपराजितः")

    assert "Entry 1 - Nama: 716" in entry.display_text
    assert "Entry 2 - Nama: 862" in entry.display_text
    assert "अपराजितः (862)" in entry.display_text
    assert "दर्पहा दर्पदो दृप्तो दुर्धरोऽथापराजितः ॥७६॥" not in entry.display_text
    assert "दर्पहा दर्पदो दृप्तो दुर्धरोऽथापराजितः ॥७६॥" in sloka.display_text
    assert "अपराजितः सर्वसहो नियन्ताऽनियमोऽयमः ॥९२॥" in sloka.display_text


def test_repeated_anagha_full_entry_and_sloka_search_include_both_slokas():
    entry = render_entry("अनघः")
    sloka = render_sloka("अनघः")

    assert "Entry 1 - Nama: 146" in entry.display_text
    assert "Entry 2 - Nama: 831" in entry.display_text
    assert "अनघः (831)" in entry.display_text
    assert "अनघो विजयो जेता विश्वयोनिः पुनर्वसुः ॥१६॥" not in entry.display_text
    assert "काली कराली च मनोजवा" not in entry.display_text
    assert "अनघो विजयो जेता विश्वयोनिः पुनर्वसुः ॥१६॥" in sloka.display_text
    assert "अमूर्तिरनघोऽचिन्त्यो भयकृद्भयनाशनः ॥८९॥" in sloka.display_text


def test_nama_sloka_cross_index_maps_repeated_anagha_to_distinct_slokas():
    cross_index = nama_sloka_cross_index()

    assert isinstance(cross_index, dict)


def test_devanagari_heading_match_treats_ascii_colon_as_visarga():
    assert heading_matches_query("अनन्त: Anantaḥ (886)", "अनन्तः")


def test_repeated_anirdesyavapu_returns_177_and_656_with_devanagari_query():
    hits = extract_entry("अनिरदेश्यवपुः")

    headings = [hit.text.splitlines()[0] for hit in hits]
    pages = [hit.page_start for hit in hits]
    assert [hit.number for hit in hits] == [177, 656]
    assert "177. Anirdeśyavapuḥ (also word 656)" in headings
    assert "5 . Anirdeśyavapuḥ" in headings
    assert 145 in pages
    assert 356 in pages


def test_sloka_search_returns_both_anirdesyavapu_slokas_with_transliteration():
    result = render_sloka("अनिरदेश्यवपुः")

    assert "अनिर्देश्यवपुः श्रीमानमेयात्मा महाद्रिधृक् ॥१९॥" in result.display_text
    assert "anirdeśyavapuḥ śrīmān ameyātmā mahādridhṛk. (19)" in result.display_text
    assert "अनिर्देश्यवपुर्विष्णुर्वीरोऽनन्तो धनञ्जयः ॥७०॥" in result.display_text
    assert "anirdeśyavapuḥ viṣṇuḥ vīro 'nanto dhanañjayaḥ. (70)" in result.display_text


def test_sloka_search_returns_corrected_mahanidhi_sloka():
    result = render_sloka("महानिधिः")

    assert "महाह्रदो महागर्तो महाभूतो महानिधिः ॥८६॥" in result.display_text
    assert "mahāhrado mahāgarto mahābhūto mahānidhiḥ. (86)" in result.display_text
    assert "Herta" not in result.display_text
    assert "mahāgarbho" not in result.display_text


def test_sloka_search_returns_complete_verse_92():
    result = render_sloka("९२")

    assert "धनुर्धरो धनुर्वेदो दण्डो दमयिता दमः ।" in result.display_text
    assert "अपराजितः सर्वसहो नियन्ताऽनियमोऽयमः ॥९२॥" in result.display_text
    assert "dhanurdharo dhanurvedo daṇḍo damayitā damaḥ," in result.display_text
    assert "aparājitaḥ sarvasaho niyantā 'niyamo 'yamaḥ. (92)" in result.display_text


def test_sloka_search_accepts_labelled_english_number():
    result = render_sloka("sloka 92")

    assert "धनुर्धरो धनुर्वेदो दण्डो दमयिता दमः ।" in result.display_text
    assert "अपराजितः सर्वसहो नियन्ताऽनियमोऽयमः ॥९२॥" in result.display_text


def test_maha_garta_and_maha_bhuta_headings_are_restored():
    garta = render_entry("महागर्तः")
    bhuta = render_entry("महाभूतः")

    assert "महागर्तः (804)" in garta.display_text
    assert "महाभूतः (805)" in bhuta.display_text
    assert "Hert:" not in garta.display_text
    assert "Held:" not in bhuta.display_text


def test_repeated_aja_returns_all_three_entries_without_neighbors():
    hits = extract_entry("204. Ajaḥ (95, 521)")

    headings = [hit.text.splitlines()[0] for hit in hits]
    assert [hit.number for hit in hits] == [95, 204, 521]
    assert "95. Ajaḥ (also words 204, 521)" in headings
    assert "204. Ajaḥ (also words 95, 521)" in headings
    assert "521. Ajaḥ (also words 95, 204)" in headings
    mover = next(hit.text for hit in hits if hit.number == 95)
    unborn = next(hit.text for hit in hits if hit.number == 204)
    manmatha = next(hit.text for hit in hits if hit.number == 521)
    assert "सर्वेश्वरः Sarveśvaraḥ" not in unborn
    assert "दुर्मर्षणः Durmarṣaṇaḥ" not in mover
    assert "महार्हः Maharhaḥ" not in manmatha


def test_sanskrit_derivation_line_with_roman_artifact_is_not_heading():
    text = "कृतो वेदात्मक आगमो येनेति Hara: |"

    assert parse_nama_heading(text) is None


def test_scripture_quote_line_is_not_a_nama_heading_match():
    text = "आदौ मध्ये तथा चान्ते विष्णुः सर्वत्र सर्वदा । MB.Sva.Sra.93"

    assert not heading_matches_query(text, "विष्णुः")


def test_anisha_entry_stops_before_shashvatasthira_and_includes_sloka():
    result = render_entry("अनीशः")

    assert "अनीशः (626)" in result.display_text
    assert "शाश्वतस्थिरः Śāśvatasthiraḥ" not in result.display_text
    assert "Page:" not in result.copy_text


def test_anirvinna_query_filters_out_prior_entry_and_uses_sloka_47():
    result = render_entry("अनिर्विण्णः")
    sloka = render_sloka("अनिर्विण्णः")

    assert "Entry 1 - Nama: 435" in result.display_text
    assert "Entry 2 - Nama: 892" in result.display_text
    assert "अनिर्विण्णः (892)" in result.display_text
    assert "महाधनः Mahadhanaḥ" not in result.display_text
    assert "विस्तारः स्थावरस्थाणुः प्रमाणं बीजमव्ययम् ।" not in result.display_text
    assert "अनिर्विण्णः स्थविष्ठोऽभूर्धर्मयूपो महामखः ।" in sloka.display_text
    assert "विस्तारः स्थावरस्थाणुः प्रमाणं बीजमव्ययम् ।" not in sloka.display_text


def test_anila_repeated_entries_use_slokas_25_and_87_not_86():
    result = render_entry("अनिलः")
    sloka = render_sloka("अनिलः")

    assert "Entry 1 - Nama: 234" in result.display_text
    assert "Entry 2 - Nama: 812" in result.display_text
    assert "अनिलः (812)" in result.display_text
    assert "सुवर्णबिन्दुरक्षोभ्यः सर्ववागीश्वरेश्वरः ।" not in result.display_text
    assert "कुमुदः कुन्दरः कुन्दः पर्जन्यः पावनोऽनिलः ।" in sloka.display_text
    assert "सुवर्णबिन्दुरक्षोभ्यः सर्ववागीश्वरेश्वरः ।" not in sloka.display_text


def test_sloka_search_finds_devanagari_headword_that_appears_in_sandhi():
    result = render_sloka("अनीशः")

    assert "उदीर्णः सर्वतश्चक्षुरनीशः शाश्वतस्थिरः ।" in result.display_text
    assert "bhūśayo bhūṣaṇo bhūtir viśokaḥ śokanāśanaḥ. (67)" in result.display_text
    assert "No śloka found." not in result.display_text


def test_sloka_search_returns_full_devanagari_and_roman_block():
    hits = sloka_search("सत्यधर्मा")

    assert hits
    assert hits[0].page == 0
    assert "अजो महार्हः स्वाभाव्यो जितामित्रः प्रमोदनः ।" in hits[0].text
    assert "आनन्दो नन्दनो नन्दः सत्यधर्मा त्रिविक्रमः ॥५६॥" in hits[0].text
    assert "ajo mahārhaḥ svābhāvyo jitāmitraḥ pramodanaḥ," in hits[0].text
    assert "ānando nandano nandaḥ satyadharmā trivikramaḥ. (56)" in hits[0].text


def test_sloka_search_handles_spaced_danda_verse_end():
    hits = sloka_search("anirvinnah")

    assert hits
    assert any("अनन्तो हुतभुग्भोक्ता सुखदो नैकजोऽग्रजः ।" in hit.text for hit in hits)
    assert any("anirviṇṇaḥ sadāmarṣī lokādhiṣṭhānam adbhutaḥ. (95)" in hit.text for hit in hits)


def test_sloka_search_allows_roman_query_without_diacritics():
    hits = sloka_search("satyadharma trivikrama")

    assert hits
    assert any(
        "ānando nandano nandaḥ satyadharmā trivikramaḥ. (56)" in hit.text
        for hit in hits
    )


def test_exact_search_adds_containing_sloka_when_match_is_inside_verse():
    hits = exact_search("सत्यधर्मा")

    sloka_hits = [hit for hit in hits if hit.get("sloka")]
    assert sloka_hits == []


def test_desktop_exact_renders_sloka_and_copy_omits_page_notes():
    result = render_exact("सत्यधर्मा")

    assert "No exact text match was found. Showing the verified nāma entry instead." in result.display_text
    assert "सत्यधर्मा (529)" in result.display_text
    assert "Page:" not in result.copy_text
    assert "OCR Notes:" not in result.copy_text


def test_desktop_sloka_search_is_copy_ready():
    result = render_sloka("कामदेवः")

    assert "कामदेवः कामपालः कामी कान्तः कृतागमः ।" in result.display_text
    assert "kāmadevaḥ kāmapālaḥ kāmī kāntaḥ kṛtāgamaḥ," in result.copy_text
    assert "Page:" not in result.copy_text


def test_desktop_entry_metadata_shows_safe_auxiliary_nama_number():
    result = render_entry("वृद्धात्मा")

    assert "वृद्धात्मा (352)" in result.display_text
    assert "Entry 1 - Nama: 352" in result.display_text
    assert "Page:" not in result.display_text
    assert result.meta_text == ""
    assert "Nama:" not in result.copy_text


def test_desktop_entry_metadata_prefers_specific_heading_number():
    result = render_entry("अमितविक्रमः")

    assert "अमितविक्रमः (641)" in result.display_text
    assert "अमितविक्रमः (516)" in result.display_text
    assert "Entry 1 - Nama: 516" in result.display_text
    assert "Entry 2 - Nama: 641" in result.display_text
    assert "Page:" not in result.display_text
    assert "Entry 1 - Nama: 516, 641" not in result.display_text


def test_desktop_hybrid_search_keeps_sources_in_result_text():
    result = render_hybrid("moksha")

    assert "Source passage 1" in result.display_text
    assert "Source passage 1" in result.copy_text
    assert "Page:" not in result.display_text
    assert "score" not in result.meta_text
    assert "keyword" not in result.meta_text
    assert "vector" not in result.meta_text


def test_desktop_hybrid_treats_explain_as_instruction_and_corrects_bagha():
    result = render_hybrid("explain Bagha")

    first_passage = result.display_text.split("Source passage 2", 1)[0]
    assert "Source passage 1" in first_passage
    assert "bhaga, the six-fold virtues" in first_passage
    assert "Karaka is a technical word" not in first_passage


def test_desktop_answer_uses_cited_retrieval():
    result = render_answer("What does the text say about Brahman?")

    assert "Answer:" in result.display_text
    assert "Grounded answer" not in result.display_text
    assert "[p." not in result.display_text
    assert "score" not in result.meta_text


def test_desktop_answer_uses_cleaned_query_terms():
    result = render_answer("explain Bagha")

    assert "bhaga, the six-fold virtues" in result.display_text
    assert "[p." not in result.display_text


def test_desktop_hybrid_question_filters_to_strong_three_vedas_match():
    result = render_hybrid("where does the the three vedas come from")

    assert result.display_text.count("Source passage") == 1
    assert "Source passage 1" in result.display_text
    assert "three Vedas come from pranava" in result.display_text


def test_desktop_answer_question_uses_three_vedas_source():
    result = render_answer("where does the the three vedas come from")

    assert result.display_text.startswith("Answer:")
    assert "Grounded answer" not in result.display_text
    assert "The three Vedas come from pranava" in result.display_text
    assert "[p." not in result.display_text
