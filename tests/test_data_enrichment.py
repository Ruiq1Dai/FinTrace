from unittest.mock import patch

from scripts.enrich_data import extract_pdf_text


def test_pdf_extractor_keeps_page_boundaries():
    class Completed:
        stdout = b"page one\fpage two"

    with patch("scripts.enrich_data.subprocess.run", return_value=Completed()):
        text, pages = extract_pdf_text(b"test")
    assert "page one" in text
    assert pages == ["page one", "page two"]
