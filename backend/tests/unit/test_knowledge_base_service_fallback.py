import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.document_loaders import detect_input_kind, infer_normalization_mode
from app.services.knowledge_base_service import (
    KnowledgeBaseService,
    _build_safe_fallback_text,
    _friendly_ingestion_error_message,
    _normalize_source_metadata,
    _sanitize_error_message,
)


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
    svc._cache_key = KnowledgeBaseService._cache_key.__get__(svc, KnowledgeBaseService)
    svc._page_asset_rel_path = KnowledgeBaseService._page_asset_rel_path.__get__(
        svc, KnowledgeBaseService
    )
    svc._crop_asset_rel_path = KnowledgeBaseService._crop_asset_rel_path.__get__(
        svc, KnowledgeBaseService
    )
    svc._render_page_image = KnowledgeBaseService._render_page_image.__get__(
        svc, KnowledgeBaseService
    )
    svc._crop_from_page = KnowledgeBaseService._crop_from_page.__get__(svc, KnowledgeBaseService)

    import tempfile
    from types import SimpleNamespace

    from app.services import knowledge_base_service as kb_module

    with tempfile.TemporaryDirectory() as tmp:
        kb_module.settings = SimpleNamespace(upload_dir=tmp)
        kb_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        Path(tmp, str(kb_id), str(doc_id), "derived", "pages").mkdir(parents=True, exist_ok=True)
        Path(tmp, str(kb_id), str(doc_id), "derived", "crops").mkdir(parents=True, exist_ok=True)
        Path(tmp, str(kb_id), str(doc_id), "derived", "cache").mkdir(parents=True, exist_ok=True)

        blocks, trace = svc._build_blocks_from_segments(
            kb_id=kb_id,
            doc_id=doc_id,
            file_name="photo.png",
            file_bytes=(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c```\x00\x00"
                b"\x00\x04\x00\x01\xa3'\xa4\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
        )

        assert len(blocks) == 1
        assert blocks[0].block_type == "image"
        assert blocks[0].page == 1
        assert blocks[0].bbox_norm == {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}
        assert blocks[0].page_image_path == "derived/pages/page-0001.png"
        assert trace["input_kind"] == "image"


def test_crop_from_page_clamps_bbox_boundaries(tmp_path, monkeypatch):
    from PIL import Image

    import app.services.knowledge_base_service as mod

    svc = KnowledgeBaseService.__new__(KnowledgeBaseService)
    svc._crop_asset_rel_path = KnowledgeBaseService._crop_asset_rel_path.__get__(
        svc, KnowledgeBaseService
    )

    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    monkeypatch.setattr(mod, "settings", type("S", (), {"upload_dir": str(tmp_path)})())
    page_dir = tmp_path / str(kb_id) / str(doc_id) / "derived" / "pages"
    page_dir.mkdir(parents=True, exist_ok=True)
    crop_dir = tmp_path / str(kb_id) / str(doc_id) / "derived" / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    page_img = page_dir / "page-0001.png"
    Image.new("RGB", (100, 100), color=(255, 255, 255)).save(page_img)

    rel = svc._crop_from_page(
        kb_id=kb_id,
        doc_id=doc_id,
        page_image_path="derived/pages/page-0001.png",
        block_id="blk-x",
        bbox_norm={"x0": -0.3, "y0": -0.2, "x1": 1.4, "y1": 1.6},
    )
    assert rel == "derived/crops/blk-x.png"
    assert (tmp_path / str(kb_id) / str(doc_id) / rel).exists()


def test_normalize_source_metadata_preserves_contract_fields():
    normalized = _normalize_source_metadata(
        {
            "page": 1,
            "block_type": "image",
            "bbox_norm": {"x0": 0.1, "y0": 0.1, "x1": 0.9, "y1": 0.9},
            "page_image_path": "derived/pages/page-0001.png",
        }
    )
    assert normalized["block_type"] == "image"
    assert normalized["bbox_norm"]["x0"] == 0.1


def test_sanitize_error_message_hides_upload_root(tmp_path, monkeypatch):
    import app.services.knowledge_base_service as mod

    monkeypatch.setattr(mod, "settings", type("S", (), {"upload_dir": str(tmp_path)})())
    raw = f"failed at {tmp_path}/abc/raw/note.txt"
    sanitized = _sanitize_error_message(raw)
    assert str(tmp_path) not in sanitized
    assert "[UPLOAD_DIR]" in sanitized


def test_replay_rate_limit_per_doc():
    svc = KnowledgeBaseService.__new__(KnowledgeBaseService)
    svc.user_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    for _ in range(5):
        svc._check_replay_rate_limit(kb_id, doc_id)
    with pytest.raises(HTTPException, match="rate limited"):
        svc._check_replay_rate_limit(kb_id, doc_id)


def test_friendly_ingestion_error_message_for_uuid_json_serialization():
    msg = _friendly_ingestion_error_message(
        TypeError("Object of type UUID is not JSON serializable")
    )
    assert "序列化错误" in msg
    assert "UUID" in msg


def test_office_auto_mode_prefers_text_extraction_before_pdf_conversion(monkeypatch):
    from app.services import knowledge_base_service as mod
    from app.services.document_loaders import ExtractedSegment

    svc = KnowledgeBaseService.__new__(KnowledgeBaseService)
    svc._cache_key = KnowledgeBaseService._cache_key.__get__(svc, KnowledgeBaseService)
    svc._page_asset_rel_path = KnowledgeBaseService._page_asset_rel_path.__get__(
        svc, KnowledgeBaseService
    )
    svc._crop_asset_rel_path = KnowledgeBaseService._crop_asset_rel_path.__get__(
        svc, KnowledgeBaseService
    )
    svc._crop_from_page = KnowledgeBaseService._crop_from_page.__get__(svc, KnowledgeBaseService)

    called = {"convert_office_to_pdf": False}

    def _fake_extract_segments(*, file_name: str, data: bytes):
        _ = (file_name, data)
        return [ExtractedSegment(text="中文段落内容", page=None)]

    def _fake_convert_office_to_pdf(*, data: bytes, suffix: str):
        _ = (data, suffix)
        called["convert_office_to_pdf"] = True
        return b"%PDF-1.7"

    monkeypatch.setattr(mod, "extract_segments", _fake_extract_segments)
    monkeypatch.setattr(mod, "convert_office_to_pdf", _fake_convert_office_to_pdf)

    import tempfile
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory() as tmp:
        mod.settings = SimpleNamespace(upload_dir=tmp)
        kb_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        Path(tmp, str(kb_id), str(doc_id), "derived", "cache").mkdir(parents=True, exist_ok=True)
        Path(tmp, str(kb_id), str(doc_id), "derived", "pages").mkdir(parents=True, exist_ok=True)
        Path(tmp, str(kb_id), str(doc_id), "derived", "crops").mkdir(parents=True, exist_ok=True)

        blocks, trace = svc._build_blocks_from_segments(
            kb_id=kb_id,
            doc_id=doc_id,
            file_name="sample.doc",
            file_bytes=b"binary-doc-content",
            retrieval_config={"multimodal_ingestion": {"parse_mode": "auto"}},
        )

    assert len(blocks) == 1
    assert blocks[0].text == "中文段落内容"
    assert blocks[0].modality == "text"
    assert called["convert_office_to_pdf"] is False
    assert trace["normalization_mode"] == "office_to_pages_blocks"
    assert trace["reason"] == "office_text_layer_available"
