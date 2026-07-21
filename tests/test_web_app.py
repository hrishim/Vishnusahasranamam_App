from vishnu_retrieval.web_app import render_search


def test_web_entry_search_returns_copy_text_without_page_footer():
    result = render_search("entry", "वृद्धात्मा")

    assert "वृद्धात्मा (352)" in result["display_text"]
    assert "Nama:" not in result["display_text"]
    assert "Page:" not in result["display_text"]
    assert "Pages:" not in result["display_text"]
    assert result["meta_text"] == ""
    assert "Page:" not in result["copy_text"]
    assert "Nama:" not in result["copy_text"]


def test_web_answer_mode_returns_grounded_answer():
    result = render_search("answer", "where does the three vedas come from")

    assert "Answer:" in result["display_text"]
    assert "Grounded answer" not in result["display_text"]
    assert "pranava" in result["display_text"]


def test_medhaja_entry_restores_heading_derivation_and_english():
    result = render_search("entry", "Medhaja")

    assert "मेधजः (753)" in result["display_text"]
    assert "मेधे - अध्वरे जायत इति मेधजः।" in result["display_text"]
    assert "Medha means a sacrifice." in result["display_text"]
    assert "undertakes the performance" in result["display_text"]
    assert "dīkṣā, the religious initiation" in result["display_text"]
    assert "MMedha" not in result["display_text"]
