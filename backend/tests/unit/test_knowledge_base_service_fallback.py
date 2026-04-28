from app.services.knowledge_base_service import _build_safe_fallback_text


def test_binary_pdf_fallback_text_is_safe_placeholder():
    raw_pdf_like = b"%PDF-1.7\n\x00\xff\x10stream\x00binary"
    text = _build_safe_fallback_text("scan.pdf", raw_pdf_like, "pdf")
    assert text.startswith("[OCR_FALLBACK_PENDING] scan.pdf")
    assert "\x00" not in text
    assert "binary/scanned content" in text


def test_text_fallback_strips_unsafe_control_chars():
    raw_text = b"hello\x01world\nline2"
    text = _build_safe_fallback_text("note.txt", raw_text, "text")
    assert text == "helloworld\nline2"
