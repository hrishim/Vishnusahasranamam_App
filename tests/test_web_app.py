from vishnu_retrieval.web_app import render_search


def test_web_entry_search_returns_copy_text_without_page_footer():
    result = render_search("entry", "वृद्धात्मा")

    assert "वृद्धात्मा Vrddhatma" in result["display_text"]
    assert "Nama: 352 | Page: 107" in result["meta_text"]
    assert "Page:" not in result["copy_text"]
    assert "Nama:" not in result["copy_text"]
