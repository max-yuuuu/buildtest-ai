from app.services.document_loaders import detect_input_kind, infer_normalization_mode
from app.services.knowledge_base_service import KnowledgeBaseService, _build_safe_fallback_text


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


def test_detect_input_kind_supports_image_and_more_office_types():
    assert detect_input_kind("slide.pptx") == "office"
    assert detect_input_kind("sheet.xlsx") == "office"
    assert detect_input_kind("photo.png") == "image"
    assert infer_normalization_mode("photo.png") == "image_to_page_block"


def test_image_input_builds_image_block_with_full_page_bbox():
    svc = KnowledgeBaseService.__new__(KnowledgeBaseService)

    blocks, trace = svc._build_blocks_from_segments(
        file_name="photo.png",
        file_bytes=b"\x89PNG\r\n\x1a\nbinary",
    )

    assert len(blocks) == 1
    assert blocks[0].block_type == "image"
    assert blocks[0].page == 1
    assert blocks[0].bbox_norm == {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}
    assert trace["input_kind"] == "image"
