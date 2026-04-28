import uuid

from app.models.document import Document
from app.services.knowledge_base_service import (
    ParsedBlock,
    _build_source_generator,
    _build_source_metadata,
)


def test_build_source_generator_records_ocr_model_lineage():
    payload = _build_source_generator(
        generator_impl="paddleocr",
        modality="ocr_text",
        config_snapshot={"ocr_model_id": str(uuid.uuid4())},
    )

    assert payload is not None
    assert payload["impl"] == "paddleocr"
    assert payload["capability"] == "ocr"
    assert "model_id" in payload
    assert isinstance(payload["model_id"], str)


def test_build_source_metadata_produces_multimodal_replay_contract():
    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        file_name="scan.pdf",
        file_type="pdf",
        storage_path="kb/doc/raw/scan.pdf",
        status="processing",
    )
    block = ParsedBlock(
        block_id="blk-1",
        block_type="image",
        page=2,
        text="ocr result",
        modality="ocr_text",
        generator_impl="paddleocr",
        bbox_norm={"x0": 0.1, "y0": 0.2, "x1": 0.7, "y1": 0.9},
        page_image_path="derived/pages/page-0002.png",
        crop_image_path="derived/crops/blk-1.png",
    )
    parse_trace = {
        "input_kind": "pdf",
        "normalization_mode": "pdf_to_pages",
        "normalized_to": "blocks",
        "config_snapshot": {"ocr_model_id": str(uuid.uuid4())},
    }

    payload = _build_source_metadata(
        doc=doc,
        block=block,
        chunk_text="1. 图片说明\nocr result",
        parse_trace=parse_trace,
    )

    assert payload["page"] == 2
    assert payload["section"] == "1. 图片说明"
    assert payload["block_type"] == "image"
    assert payload["block_id"] == "blk-1"
    assert payload["asset_id"] == f"asset:{doc.id}:blk-1"
    assert payload["bbox_norm"] == {"x0": 0.1, "y0": 0.2, "x1": 0.7, "y1": 0.9}
    assert payload["page_image_path"] == "derived/pages/page-0002.png"
    assert payload["crop_image_path"] == "derived/crops/blk-1.png"
    assert payload["modality"] == "ocr_text"
    assert payload["generator"]["capability"] == "ocr"
    assert isinstance(payload["generator"]["model_id"], str)
    assert payload["origin"]["file_name"] == "scan.pdf"
    assert payload["origin"]["input_kind"] == "pdf"
    assert payload["context"]["chunk_block_ref"]["block_id"] == "blk-1"
