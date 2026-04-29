from __future__ import annotations

import hashlib
import io
import json
import logging
import mimetypes
import os
import shutil
import string
import time
import time as time_module
import uuid
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.kb_vector_chunk import KbVectorChunk
from app.models.knowledge_base import KnowledgeBase
from app.models.model import Model
from app.models.provider import Provider
from app.models.vector_db_config import VectorDbConfig
from app.repositories.document import DocumentRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.model import ModelRepository
from app.repositories.provider import ProviderRepository
from app.repositories.vector_db_config import VectorDbConfigRepository
from app.schemas.knowledge_base import (
    BatchUploadResponse,
    BBoxNorm,
    DocumentChunkDocumentRead,
    DocumentChunkPaginationRead,
    DocumentChunkRead,
    DocumentChunksResponse,
    DocumentChunkSummaryRead,
    DocumentRead,
    IngestionJobRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
    RebuildRequest,
    RetrieveHit,
    RetrieveRequest,
    RetrieveResponse,
    SourceGenerator,
    SourceMetadata,
    SourceOrigin,
)
from app.services import embedding_client, ocr_client
from app.services.document_loaders import (
    convert_office_to_pdf,
    detect_input_kind,
    extract_segments,
    infer_normalization_mode,
    infer_section_title,
)
from app.services.ingestion_job_service import IngestionJobService
from app.services.notification_service import NotificationService
from app.services.retrieval_strategy import get_retrieval_strategy
from app.services.vector_connector import VectorChunkItem, vector_connector_for_config

logger = logging.getLogger(__name__)


def _collection_key(kb: KnowledgeBase, db_type: str) -> str:
    if db_type == "postgres_pgvector":
        return str(kb.id)
    return kb.collection_name


def _make_collection_name(kb_id: uuid.UUID, dim: int) -> str:
    return f"kb_{kb_id.hex}_{dim}"


def _estimate_token_length(text: str) -> int:
    words = text.split()
    if len(words) >= max(1, len(text) // 8):
        return len(words)
    return max(1, ceil(len(text) / 2))


def _multimodal_ingestion_config(retrieval_config: dict | None) -> dict:
    cfg = (retrieval_config or {}).get("multimodal_ingestion", {})
    return {
        "ocr_model_id": cfg.get("ocr_model_id"),
        "enable_vlm": bool(cfg.get("enable_vlm", False)),
        "languages": list(cfg.get("languages", [])),
        "parse_mode": cfg.get("parse_mode", "auto"),
    }


def _normalize_retrieval_config(retrieval_config: dict | None) -> dict:
    base = dict(retrieval_config or {})
    base["multimodal_ingestion"] = _multimodal_ingestion_config(base)
    return base


MAX_REPLAY_ASSET_BYTES = 20 * 1024 * 1024
MAX_FALLBACK_TEXT_CHARS = 2000
REPLAY_ASSET_RPS = 5
_replay_access_lock = Lock()
_replay_access_tracker: dict[str, tuple[int, float]] = {}


@dataclass
class ParsedBlock:
    block_id: str
    block_type: str
    page: int | None
    text: str
    modality: str
    generator_impl: str
    bbox_norm: dict[str, float] | None = None
    page_image_path: str | None = None
    crop_image_path: str | None = None
    context_text: str | None = None
    ocr_lines: list[dict] | None = None
    ocr_words: list[dict] | None = None


def _build_source_generator(
    *,
    generator_impl: str,
    modality: str,
    config_snapshot: dict | None = None,
) -> dict | None:
    generator = SourceGenerator(impl=generator_impl)
    if modality.startswith("ocr"):
        generator.capability = "ocr"
        ocr_model_id = (config_snapshot or {}).get("ocr_model_id")
        if ocr_model_id:
            try:
                generator.model_id = uuid.UUID(str(ocr_model_id))
            except ValueError:
                generator.model_id = None
    payload = generator.model_dump(mode="json", exclude_none=True)
    return payload or None


def _build_source_metadata(
    *,
    doc: Document,
    block: ParsedBlock,
    chunk_text: str,
    parse_trace: dict,
) -> dict:
    asset_id = f"asset:{doc.id}:{block.block_id}"
    section = infer_section_title(chunk_text)
    bbox = BBoxNorm.model_validate(block.bbox_norm).model_dump() if block.bbox_norm else None
    metadata = SourceMetadata(
        page=block.page,
        section=section,
        block_type=block.block_type,
        block_id=block.block_id,
        asset_id=asset_id,
        bbox_norm=bbox,
        page_image_path=block.page_image_path,
        crop_image_path=block.crop_image_path,
        modality=block.modality,
        generator=_build_source_generator(
            generator_impl=block.generator_impl,
            modality=block.modality,
            config_snapshot=parse_trace.get("config_snapshot"),
        ),
        origin=SourceOrigin(
            file_name=doc.file_name,
            file_type=doc.file_type,
            storage_path=doc.storage_path,
            input_kind=parse_trace.get("input_kind"),
            normalization_mode=parse_trace.get("normalization_mode"),
            normalized_to=parse_trace.get("normalized_to"),
        ),
        context={
            "parse_trace": parse_trace,
            "chunk_block_ref": {
                "document_id": str(doc.id),
                "block_id": block.block_id,
                "asset_id": asset_id,
            },
            "ocr": {
                "lines": (block.ocr_lines or [])[:100],
                "words": (block.ocr_words or [])[:200],
            },
            "surrounding_text": block.context_text,
        },
    )
    # Use JSON mode to ensure UUID/datetime are JSON-serializable for JSON columns.
    return metadata.model_dump(mode="json", exclude_none=True)


def _normalize_source_metadata(payload: dict | None) -> dict:
    if not payload:
        return {}
    return SourceMetadata.model_validate(payload).model_dump(mode="json", exclude_none=True)


def _sanitize_error_message(raw: str) -> str:
    sanitized = raw.replace(str(Path(settings.upload_dir).resolve()), "[UPLOAD_DIR]")
    return sanitized[:2000]


def _friendly_ingestion_error_message(exc: Exception) -> str:
    raw = str(exc)
    lower = raw.lower()

    if "object of type uuid is not json serializable" in lower:
        return (
            "文档入库失败：系统内部元数据序列化错误（UUID 无法写入 JSON）。"
            "请重试；若持续出现，请升级后端到最新版本或联系管理员。"
        )

    if "vector dimension" in lower or "维度" in raw:
        return (
            "文档入库失败：embedding 向量维度不一致。"
            "请检查知识库绑定的 embedding 模型维度配置是否与上游实际输出一致。"
        )

    if "ocr provider" in lower or ("ocr" in lower and "not available" in lower):
        return (
            "文档入库失败：OCR provider/model 不可用，"
            "请检查 provider 是否启用与 base_url/api_key 配置。"
        )

    # Default: keep it short and readable; full details stay in server logs.
    brief = _sanitize_error_message(raw)
    if len(brief) > 300:
        brief = brief[:300] + "..."
    return f"文档入库失败：{brief}"


def _doc_root_dir(kb_id: uuid.UUID, doc_id: uuid.UUID) -> Path:
    return Path(settings.upload_dir) / str(kb_id) / str(doc_id)


def _doc_raw_dir(kb_id: uuid.UUID, doc_id: uuid.UUID) -> Path:
    return _doc_root_dir(kb_id, doc_id) / "raw"


def _doc_derived_dir(kb_id: uuid.UUID, doc_id: uuid.UUID) -> Path:
    return _doc_root_dir(kb_id, doc_id) / "derived"


def _doc_pages_dir(kb_id: uuid.UUID, doc_id: uuid.UUID) -> Path:
    return _doc_derived_dir(kb_id, doc_id) / "pages"


def _doc_crops_dir(kb_id: uuid.UUID, doc_id: uuid.UUID) -> Path:
    return _doc_derived_dir(kb_id, doc_id) / "crops"


def _doc_cache_dir(kb_id: uuid.UUID, doc_id: uuid.UUID) -> Path:
    return _doc_derived_dir(kb_id, doc_id) / "cache"


def _strip_unsafe_text_chars(text: str) -> str:
    allowed_controls = {"\n", "\r", "\t"}
    cleaned = "".join(ch for ch in text if ch in allowed_controls or (ch >= " " and ch != "\x7f"))
    return cleaned.replace("\x00", "")


def _looks_binary_bytes(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:4096]
    if b"\x00" in sample:
        return True
    textish = sum(1 for b in sample if chr(b) in string.printable or b >= 0x80)
    return (textish / len(sample)) < 0.85


def _build_safe_fallback_text(file_name: str, file_bytes: bytes, input_kind: str) -> str:
    if input_kind in {"pdf", "office", "image"} or _looks_binary_bytes(file_bytes):
        return (
            f"[OCR_FALLBACK_PENDING] {file_name}\n"
            "Document appears to be binary/scanned content without an extractable text layer yet."
        )

    decoded = file_bytes.decode("utf-8", errors="replace")
    cleaned = _strip_unsafe_text_chars(decoded).strip()
    if not cleaned:
        return f"[OCR_FALLBACK_PENDING] {file_name}"
    return cleaned[:MAX_FALLBACK_TEXT_CHARS]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bbox_from_pdf_obj(
    *, x0: float, y0: float, x1: float, y1: float, width: float, height: float
) -> dict[str, float]:
    safe_w = max(1.0, float(width))
    safe_h = max(1.0, float(height))
    top = safe_h - float(y1)
    bottom = safe_h - float(y0)
    return {
        "x0": _clamp01(float(x0) / safe_w),
        "y0": _clamp01(top / safe_h),
        "x1": _clamp01(float(x1) / safe_w),
        "y1": _clamp01(bottom / safe_h),
    }


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.kb_repo = KnowledgeBaseRepository(session, user_id)
        self.doc_repo = DocumentRepository(session, user_id)
        self.vdb_repo = VectorDbConfigRepository(session, user_id)
        self.model_repo = ModelRepository(session, user_id)
        self.provider_repo = ProviderRepository(session, user_id)
        self.ingestion_job_service = IngestionJobService(session, user_id)
        self.notification_service = NotificationService(session, user_id)

    async def _get_vdbc(self, config_id: uuid.UUID) -> VectorDbConfig:
        row = await self.vdb_repo.get(config_id)
        if row is None:
            raise HTTPException(status_code=404, detail="vector db config not found")
        return row

    async def _get_embedding_model(self, model_pk: uuid.UUID) -> Model:
        m = await self.model_repo.get(model_pk)
        if m is None:
            raise HTTPException(status_code=404, detail="embedding model not found")
        if m.model_type != "embedding":
            raise HTTPException(status_code=422, detail="model must be embedding type")
        if m.vector_dimension is None:
            raise HTTPException(status_code=422, detail="embedding model missing vector_dimension")
        return m

    async def _get_ocr_model(self, model_pk: uuid.UUID) -> Model:
        m = await self.model_repo.get(model_pk)
        if m is None:
            raise HTTPException(status_code=404, detail="ocr model not found")
        if m.model_type != "ocr":
            raise HTTPException(status_code=422, detail="model must be ocr type")
        return m

    def _to_kb_read(self, kb: KnowledgeBase, doc_count: int = 0) -> KnowledgeBaseRead:
        emb_id = kb.embedding_model_id
        if emb_id is None:
            raise HTTPException(status_code=500, detail="knowledge base missing embedding model")
        return KnowledgeBaseRead(
            id=kb.id,
            user_id=kb.user_id,
            name=kb.name,
            description=kb.description,
            vector_db_config_id=kb.vector_db_config_id,
            collection_name=kb.collection_name,
            embedding_model_id=emb_id,
            embedding_dimension=kb.embedding_dimension,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            retrieval_top_k=kb.retrieval_top_k,
            retrieval_similarity_threshold=kb.retrieval_similarity_threshold,
            retrieval_config=kb.retrieval_config or {},
            document_count=doc_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )

    async def _to_doc_read(self, d: Document) -> DocumentRead:
        latest_job = await self.ingestion_job_service.repo.get_latest_for_document(
            d.knowledge_base_id, d.id
        )
        data = DocumentRead.model_validate(d).model_dump()
        if latest_job is not None:
            data["ingestion_job_id"] = latest_job.id
            data["ingestion_job_status"] = latest_job.status
            data["ingestion_attempt_count"] = latest_job.attempt_count
        return DocumentRead.model_validate(data)

    async def list(self) -> list[KnowledgeBaseRead]:
        items = await self.kb_repo.list()
        out: list[KnowledgeBaseRead] = []
        for kb in items:
            cnt = await self.doc_repo.count_for_kb(kb.id)
            out.append(self._to_kb_read(kb, cnt))
        return out

    async def create(self, data: KnowledgeBaseCreate) -> KnowledgeBaseRead:
        vdbc = await self._get_vdbc(data.vector_db_config_id)
        if vdbc.db_type not in ("postgres_pgvector", "qdrant"):
            raise HTTPException(status_code=422, detail="该向量库类型暂不支持知识库写入")
        m = await self._get_embedding_model(data.embedding_model_id)
        kb_id = uuid.uuid4()
        dim = m.vector_dimension
        assert dim is not None
        retrieval_config = await self._validate_multimodal_config(data.retrieval_config)
        kb = KnowledgeBase(
            id=kb_id,
            name=data.name,
            description=data.description,
            vector_db_config_id=data.vector_db_config_id,
            collection_name=_make_collection_name(kb_id, dim),
            embedding_model_id=data.embedding_model_id,
            embedding_dimension=dim,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
            retrieval_top_k=data.retrieval_top_k,
            retrieval_similarity_threshold=data.retrieval_similarity_threshold,
            retrieval_config=retrieval_config,
        )
        await self.kb_repo.create(kb)
        await self.session.commit()
        await self.session.refresh(kb)
        return self._to_kb_read(kb, 0)

    async def get(self, kb_id: uuid.UUID) -> KnowledgeBaseRead:
        kb = await self.kb_repo.get(kb_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="knowledge base not found")
        cnt = await self.doc_repo.count_for_kb(kb_id)
        return self._to_kb_read(kb, cnt)

    async def update(self, kb_id: uuid.UUID, data: KnowledgeBaseUpdate) -> KnowledgeBaseRead:
        kb = await self.kb_repo.get(kb_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="knowledge base not found")
        if kb.embedding_model_id is None:
            raise HTTPException(status_code=500, detail="knowledge base missing embedding model")
        if data.embedding_model_id is not None and data.embedding_model_id != kb.embedding_model_id:
            if await self.doc_repo.count_for_kb(kb_id) > 0:
                raise HTTPException(
                    status_code=409,
                    detail="已有文档时禁止更换 embedding 模型，请新建知识库或清空文档",
                )
            m = await self._get_embedding_model(data.embedding_model_id)
            dim = m.vector_dimension
            assert dim is not None
            kb.embedding_model_id = data.embedding_model_id
            if dim != kb.embedding_dimension:
                kb.embedding_dimension = dim
                kb.collection_name = _make_collection_name(kb.id, dim)
        if data.name is not None:
            kb.name = data.name
        if data.description is not None:
            kb.description = data.description
        if data.chunk_size is not None:
            kb.chunk_size = data.chunk_size
        if data.chunk_overlap is not None:
            kb.chunk_overlap = data.chunk_overlap
        if data.retrieval_top_k is not None:
            kb.retrieval_top_k = data.retrieval_top_k
        if data.retrieval_similarity_threshold is not None:
            kb.retrieval_similarity_threshold = data.retrieval_similarity_threshold
        if data.retrieval_config is not None:
            kb.retrieval_config = await self._validate_multimodal_config(data.retrieval_config)
        if kb.chunk_overlap >= kb.chunk_size:
            raise HTTPException(status_code=422, detail="chunk_overlap 必须小于 chunk_size")
        await self.kb_repo.save(kb)
        await self.session.commit()
        await self.session.refresh(kb)
        cnt = await self.doc_repo.count_for_kb(kb_id)
        return self._to_kb_read(kb, cnt)

    async def delete(self, kb_id: uuid.UUID) -> None:
        kb = await self.kb_repo.get(kb_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="knowledge base not found")
        vdbc = await self._get_vdbc(kb.vector_db_config_id)
        conn = vector_connector_for_config(vdbc, self.session)
        key = _collection_key(kb, vdbc.db_type)
        try:
            await conn.delete_by_knowledge_base(key, kb.id)
        except Exception as e:
            _ = e
        for d in await self.doc_repo.list_for_kb(kb_id):
            await self.doc_repo.soft_delete(d)
        await self.kb_repo.soft_delete(kb)
        await self.session.commit()

    async def list_documents(self, kb_id: uuid.UUID) -> list[DocumentRead]:
        await self._require_kb(kb_id)
        docs = await self.doc_repo.list_for_kb(kb_id)
        out: list[DocumentRead] = []
        for d in docs:
            out.append(await self._to_doc_read(d))
        return out

    async def _require_kb(self, kb_id: uuid.UUID) -> KnowledgeBase:
        kb = await self.kb_repo.get(kb_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="knowledge base not found")
        return kb

    async def _validate_multimodal_config(self, retrieval_config: dict | None) -> dict:
        normalized = _normalize_retrieval_config(retrieval_config)
        multimodal_cfg = normalized.get("multimodal_ingestion", {})
        ocr_model_id = multimodal_cfg.get("ocr_model_id")
        if ocr_model_id:
            try:
                ocr_model_uuid = uuid.UUID(str(ocr_model_id))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="ocr_model_id 不是合法 UUID") from exc
            await self._get_ocr_model(ocr_model_uuid)
            multimodal_cfg["ocr_model_id"] = str(ocr_model_uuid)
        normalized["multimodal_ingestion"] = multimodal_cfg
        return normalized

    def _ensure_doc_dirs(self, kb_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        _doc_raw_dir(kb_id, doc_id).mkdir(parents=True, exist_ok=True)
        _doc_pages_dir(kb_id, doc_id).mkdir(parents=True, exist_ok=True)
        _doc_crops_dir(kb_id, doc_id).mkdir(parents=True, exist_ok=True)
        _doc_cache_dir(kb_id, doc_id).mkdir(parents=True, exist_ok=True)

    def _cleanup_doc_derived_assets(self, kb_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        derived_dir = _doc_derived_dir(kb_id, doc_id)
        if derived_dir.exists():
            shutil.rmtree(derived_dir)
        self._ensure_doc_dirs(kb_id, doc_id)

    def _cleanup_doc_all_assets(self, kb_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        root_dir = _doc_root_dir(kb_id, doc_id)
        if root_dir.exists():
            shutil.rmtree(root_dir)

    def _resolve_replay_asset_path(
        self, kb_id: uuid.UUID, doc_id: uuid.UUID, asset_path: str
    ) -> Path:
        raw_asset_path = (asset_path or "").strip()
        if not raw_asset_path:
            raise HTTPException(status_code=422, detail="asset_path 不能为空")
        rel_path = Path(raw_asset_path)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise HTTPException(status_code=422, detail="asset_path 非法")
        allowed_prefixes: set[Path] = {
            Path("derived/pages"),
            Path("derived/crops"),
        }
        if not any(
            rel_path.parts[: len(prefix.parts)] == prefix.parts for prefix in allowed_prefixes
        ):
            raise HTTPException(status_code=422, detail="仅允许访问 derived/pages 或 derived/crops")
        root_dir = _doc_root_dir(kb_id, doc_id).resolve()
        resolved = (root_dir / rel_path).resolve()
        try:
            resolved.relative_to(root_dir)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="asset_path 超出文档目录") from exc
        return resolved

    def _check_replay_rate_limit(self, kb_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        key = f"{self.user_id}:{kb_id}:{doc_id}"
        now = time_module.monotonic()
        with _replay_access_lock:
            count, window_start = _replay_access_tracker.get(key, (0, now))
            if now - window_start >= 1.0:
                count = 0
                window_start = now
            count += 1
            _replay_access_tracker[key] = (count, window_start)
        if count > REPLAY_ASSET_RPS:
            raise HTTPException(status_code=429, detail="replay asset request rate limited")

    def _cache_key(self, file_bytes: bytes, config_snapshot: dict) -> str:
        payload = json.dumps(config_snapshot, ensure_ascii=True, sort_keys=True)
        return hashlib.sha256(file_bytes + payload.encode("utf-8")).hexdigest()

    def _page_asset_rel_path(self, page: int) -> str:
        return f"derived/pages/page-{page:04d}.png"

    def _crop_asset_rel_path(self, block_id: str) -> str:
        return f"derived/crops/{block_id}.png"

    def _render_page_image(
        self, *, kb_id: uuid.UUID, doc_id: uuid.UUID, page: int, source_bytes: bytes
    ) -> str:
        rel = self._page_asset_rel_path(page)
        out = _doc_root_dir(kb_id, doc_id) / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            with Image.open(io.BytesIO(source_bytes)) as img:
                img.convert("RGB").save(out, format="PNG")
        return rel

    def _crop_from_page(
        self,
        *,
        kb_id: uuid.UUID,
        doc_id: uuid.UUID,
        page_image_path: str,
        block_id: str,
        bbox_norm: dict[str, float] | None,
    ) -> str | None:
        if not bbox_norm:
            return None
        rel = self._crop_asset_rel_path(block_id)
        out = _doc_root_dir(kb_id, doc_id) / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            return rel
        page_path = _doc_root_dir(kb_id, doc_id) / page_image_path
        if not page_path.exists():
            return None
        with Image.open(page_path) as img:
            w, h = img.size
            x0 = max(0, min(w, int(_clamp01(bbox_norm["x0"]) * w)))
            y0 = max(0, min(h, int(_clamp01(bbox_norm["y0"]) * h)))
            x1 = max(x0 + 1, min(w, int(_clamp01(bbox_norm["x1"]) * w)))
            y1 = max(y0 + 1, min(h, int(_clamp01(bbox_norm["y1"]) * h)))
            img.crop((x0, y0, x1, y1)).save(out, format="PNG")
        return rel

    def _build_multimodal_chunk_text(self, block: ParsedBlock) -> str:
        if block.block_type == "text":
            return block.text
        lines = [f"[{block.block_type.upper()} BLOCK]"]
        if block.context_text:
            lines.append(f"Context: {block.context_text}")
        lines.append(f"OCR: {block.text.strip() or '[EMPTY]'}")
        return "\n".join(lines)

    async def _resolve_ocr_runtime(
        self, retrieval_config: dict | None
    ) -> tuple[Model | None, Provider | None, list[str]]:
        cfg = _multimodal_ingestion_config(retrieval_config)
        raw_languages = cfg.get("languages") or []
        languages = [str(item) for item in raw_languages if str(item).strip()] or ["zh", "en"]
        ocr_model_id = cfg.get("ocr_model_id")
        if not ocr_model_id:
            return None, None, languages
        model = await self._get_ocr_model(uuid.UUID(str(ocr_model_id)))
        provider = await self.provider_repo.get(model.provider_id)
        if provider is None or not provider.is_active:
            raise HTTPException(status_code=422, detail="OCR provider 不可用")
        return model, provider, languages

    async def _enrich_blocks_with_ocr(
        self,
        *,
        kb: KnowledgeBase,
        doc: Document,
        blocks: list[ParsedBlock],
    ) -> tuple[list[ParsedBlock], str]:
        model, provider, languages = await self._resolve_ocr_runtime(kb.retrieval_config)
        if model is None or provider is None:
            return blocks, "ocr_disabled"
        hard_failed = False
        ok_logs_left = 3
        for block in blocks:
            if hard_failed:
                break
            should_ocr = block.block_type in {"image", "table", "equation"} or block.modality in {
                "ocr_fallback_pending"
            }
            if not should_ocr:
                continue
            image_rel = block.crop_image_path or block.page_image_path
            if not image_rel:
                continue
            image_abs = _doc_root_dir(kb.id, doc.id) / image_rel
            if not image_abs.exists():
                continue
            try:
                image_bytes = image_abs.read_bytes()
                cache_key = hashlib.sha256(
                    (model.model_id + "|" + ",".join(languages)).encode("utf-8")
                    + b"|"
                    + image_rel.encode("utf-8")
                    + b"|"
                    + image_bytes
                ).hexdigest()
                cache_path = _doc_cache_dir(kb.id, doc.id) / f"ocr-{cache_key}.json"
                if cache_path.exists():
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                    cached_text = str(cached.get("text") or "").strip()
                    if cached_text:
                        block.text = cached_text
                        block.modality = "ocr_text"
                    block.generator_impl = str(cached.get("generator_impl") or "ocr.cache")
                    block.ocr_lines = (
                        cached.get("lines") if isinstance(cached.get("lines"), list) else []
                    )
                    block.ocr_words = (
                        cached.get("words") if isinstance(cached.get("words"), list) else []
                    )
                    continue

                ocr = await ocr_client.extract_text_from_image(
                    provider_type=provider.provider_type,
                    api_key=provider.api_key_encrypted,
                    base_url=provider.base_url,
                    model_id=model.model_id,
                    image_bytes=image_bytes,
                    languages=languages,
                )
                if ocr.text.strip():
                    block.text = ocr.text.strip()
                    block.modality = "ocr_text"
                block.generator_impl = ocr.provider_impl
                block.ocr_lines = ocr.lines
                block.ocr_words = ocr.words

                cache_path.write_text(
                    json.dumps(
                        {
                            "text": block.text,
                            "lines": block.ocr_lines or [],
                            "words": block.ocr_words or [],
                            "generator_impl": block.generator_impl,
                        },
                        ensure_ascii=True,
                    ),
                    encoding="utf-8",
                )

                # Keep logs bounded; enough to confirm "200 OK but empty content" vs success.
                if ok_logs_left > 0:
                    ok_logs_left -= 1
                    logger.info(
                        "ocr_enrichment_ok",
                        extra={
                            "kb_id": str(kb.id),
                            "doc_id": str(doc.id),
                            "block_id": block.block_id,
                            "image_rel": image_rel,
                            "text_len": len(block.text or ""),
                            "generator_impl": block.generator_impl,
                        },
                    )
            except Exception as exc:
                msg = str(exc)
                logger.warning("ocr_enrichment_failed", extra={"error": msg[:300]})
                # If endpoint is wrong (404), stop retrying for each block to reduce noise/cost.
                if "HTTP 404" in msg:
                    hard_failed = True
                    return blocks, "ocr_endpoint_not_found"
        return blocks, "ocr_model_applied"

    def _build_blocks_from_segments(
        self,
        *,
        kb_id: uuid.UUID,
        doc_id: uuid.UUID,
        file_name: str,
        file_bytes: bytes,
        retrieval_config: dict | None = None,
    ) -> tuple[list[ParsedBlock], dict]:
        input_kind = detect_input_kind(file_name)
        normalization_mode = infer_normalization_mode(file_name)
        multimodal_config = _multimodal_ingestion_config(retrieval_config)
        cache_key = self._cache_key(file_bytes, multimodal_config)
        cache_path = _doc_cache_dir(kb_id, doc_id) / f"parse-{cache_key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            blocks = [ParsedBlock(**item) for item in cached["blocks"]]
            return blocks, cached["trace"]

        parse_mode = str(multimodal_config.get("parse_mode") or "auto")
        blocks: list[ParsedBlock] = []
        used_mode = "txt"
        reason = "text_layer_available"
        try:
            if input_kind == "office":
                office_segments = extract_segments(file_name=file_name, data=file_bytes)
                blocks = [
                    ParsedBlock(
                        block_id=f"blk-{idx}",
                        block_type="text",
                        page=seg.page or 1,
                        text=seg.text,
                        modality="text",
                        generator_impl="extract_segments",
                        bbox_norm={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                    )
                    for idx, seg in enumerate(office_segments)
                    if seg.text and seg.text.strip()
                ]
                needs_office_pdf_fallback = parse_mode == "ocr" or not blocks
                if needs_office_pdf_fallback:
                    office_ext = file_name.rsplit(".", 1)[-1].lower()
                    file_bytes = convert_office_to_pdf(data=file_bytes, suffix=office_ext)
                    input_kind = "pdf"
                    normalization_mode = "office_to_pdf_to_pages_blocks"
                    reason = "office_converted_to_pdf"
                else:
                    used_mode = "txt"
                    reason = "office_text_layer_available"
            if input_kind == "image":
                page_image_path = self._render_page_image(
                    kb_id=kb_id, doc_id=doc_id, page=1, source_bytes=file_bytes
                )
                blocks.append(
                    ParsedBlock(
                        block_id="blk-image-1",
                        block_type="image",
                        page=1,
                        text=_build_safe_fallback_text(file_name, file_bytes, "image"),
                        modality="ocr_text",
                        generator_impl="image.page_placeholder",
                        bbox_norm={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                        page_image_path=page_image_path,
                    )
                )
                used_mode = "ocr"
                reason = "single_image_document"
            elif input_kind == "pdf":
                import pdfplumber

                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    for page_idx, page in enumerate(pdf.pages, start=1):
                        width = float(page.width or 1)
                        height = float(page.height or 1)
                        text = (page.extract_text() or "").strip()
                        page_image_path = self._page_asset_rel_path(page_idx)
                        page_img_abs = _doc_root_dir(kb_id, doc_id) / page_image_path
                        if not page_img_abs.exists():
                            render = page.to_image(resolution=120)
                            render.original.save(page_img_abs, format="PNG")
                        if text and parse_mode in {"auto", "txt"}:
                            blocks.append(
                                ParsedBlock(
                                    block_id=f"blk-text-{page_idx}",
                                    block_type="text",
                                    page=page_idx,
                                    text=text,
                                    modality="text",
                                    generator_impl="pdfplumber.extract_text",
                                    bbox_norm={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                                    page_image_path=page_image_path,
                                )
                            )
                        if parse_mode in {"auto", "ocr"}:
                            for img_idx, img_obj in enumerate(page.images):
                                bbox = _bbox_from_pdf_obj(
                                    x0=float(img_obj.get("x0", 0.0)),
                                    y0=float(img_obj.get("y0", 0.0)),
                                    x1=float(img_obj.get("x1", width)),
                                    y1=float(img_obj.get("y1", height)),
                                    width=width,
                                    height=height,
                                )
                                blocks.append(
                                    ParsedBlock(
                                        block_id=f"blk-image-{page_idx}-{img_idx}",
                                        block_type="image",
                                        page=page_idx,
                                        text=text[:500]
                                        or _build_safe_fallback_text(file_name, file_bytes, "pdf"),
                                        modality="ocr_text",
                                        generator_impl="pdfplumber.image_block",
                                        bbox_norm=bbox,
                                        page_image_path=page_image_path,
                                    )
                                )
                if not blocks:
                    used_mode = "ocr"
                    reason = "no_text_layer_ocr_fallback"
                    blocks.append(
                        ParsedBlock(
                            block_id="blk-fallback-0",
                            block_type="text",
                            page=1,
                            text=_build_safe_fallback_text(file_name, file_bytes, "pdf"),
                            modality="ocr_fallback_pending",
                            generator_impl="fallback.decode_or_placeholder",
                            bbox_norm={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                            page_image_path=self._page_asset_rel_path(1),
                        )
                    )
            elif input_kind != "office":
                segments = extract_segments(file_name=file_name, data=file_bytes)
                blocks = [
                    ParsedBlock(
                        block_id=f"blk-{idx}",
                        block_type="text",
                        page=seg.page or 1,
                        text=seg.text,
                        modality="text",
                        generator_impl="extract_segments",
                        bbox_norm={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                    )
                    for idx, seg in enumerate(segments)
                    if seg.text and seg.text.strip()
                ]
        except Exception:
            blocks = []

        text_by_page: dict[int, str] = {}
        for block in blocks:
            if block.block_type == "text" and block.page:
                text_by_page[block.page] = (block.text or "")[:300]
        for block in blocks:
            if block.block_type != "text":
                current = text_by_page.get(block.page or 1, "")
                around = [current]
                if block.page and block.page > 1:
                    around.append(text_by_page.get(block.page - 1, ""))
                around.append(text_by_page.get((block.page or 1) + 1, ""))
                block.context_text = " ".join([p for p in around if p]).strip()[:400]
                page_img = block.page_image_path or self._page_asset_rel_path(block.page or 1)
                block.crop_image_path = self._crop_from_page(
                    kb_id=kb_id,
                    doc_id=doc_id,
                    page_image_path=page_img,
                    block_id=block.block_id,
                    bbox_norm=block.bbox_norm,
                )

        if not blocks:
            fallback_text = _build_safe_fallback_text(file_name, file_bytes, input_kind)
            blocks = [
                ParsedBlock(
                    block_id="blk-fallback-0",
                    block_type="text",
                    page=1,
                    text=fallback_text,
                    modality="ocr_fallback_pending",
                    generator_impl="fallback.decode_or_placeholder",
                    bbox_norm={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
                )
            ]
            used_mode = "ocr"
            reason = "empty_text_layer_fallback"

        trace = {
            "mode": used_mode,
            "reason": reason,
            "input_kind": input_kind,
            "normalization_mode": normalization_mode,
            "normalized_to": "blocks",
            "config_snapshot": multimodal_config,
        }
        cache_path.write_text(
            json.dumps(
                {
                    "trace": trace,
                    "blocks": [
                        {
                            "block_id": b.block_id,
                            "block_type": b.block_type,
                            "page": b.page,
                            "text": b.text,
                            "modality": b.modality,
                            "generator_impl": b.generator_impl,
                            "bbox_norm": b.bbox_norm,
                            "page_image_path": b.page_image_path,
                            "crop_image_path": b.crop_image_path,
                            "context_text": b.context_text,
                        }
                        for b in blocks
                    ],
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        return blocks, trace

    async def upload_document(self, kb_id: uuid.UUID, file: UploadFile) -> DocumentRead:
        kb = await self._require_kb(kb_id)
        raw_name = file.filename or "upload.bin"
        safe_name = os.path.basename(raw_name)
        if not safe_name or safe_name in (".", ".."):
            raise HTTPException(status_code=422, detail="无效文件名")
        max_b = settings.upload_max_size_mb * 1024 * 1024
        data = await file.read()
        if len(data) > max_b:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过 {settings.upload_max_size_mb}MB 限制",
            )
        ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        doc = Document(
            knowledge_base_id=kb_id,
            file_name=safe_name,
            file_type=ext or None,
            file_size=len(data),
            status="queued",
        )
        await self.doc_repo.create(doc)
        await self.session.flush()
        self._ensure_doc_dirs(kb_id, doc.id)
        dest = _doc_raw_dir(kb_id, doc.id) / safe_name
        dest.write_bytes(data)
        rel = str(dest.relative_to(Path(settings.upload_dir)))
        doc.storage_path = rel
        job = await self.ingestion_job_service.create_job(kb.id, doc.id)
        await self.session.commit()
        await self.session.refresh(doc)
        from app.tasks.ingestion import process_document_ingestion_task

        process_document_ingestion_task.delay(
            str(self.user_id),
            str(kb.id),
            str(doc.id),
            str(job.id),
        )
        return await self._to_doc_read(doc)

    async def upload_documents(
        self, kb_id: uuid.UUID, files: list[UploadFile]
    ) -> BatchUploadResponse:
        kb = await self._require_kb(kb_id)
        if not files:
            raise HTTPException(status_code=422, detail="未提供文件")

        max_b = settings.upload_max_size_mb * 1024 * 1024
        doc_ids: list[uuid.UUID] = []
        job_ids: list[uuid.UUID] = []

        for file in files:
            raw_name = file.filename or "upload.bin"
            safe_name = os.path.basename(raw_name)
            if not safe_name or safe_name in (".", ".."):
                raise HTTPException(status_code=422, detail=f"无效文件名: {raw_name}")
            data = await file.read()
            if len(data) > max_b:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件「{safe_name}」超过 {settings.upload_max_size_mb}MB 限制",
                )
            ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
            doc = Document(
                knowledge_base_id=kb_id,
                file_name=safe_name,
                file_type=ext or None,
                file_size=len(data),
                status="queued",
            )
            await self.doc_repo.create(doc)
            await self.session.flush()
            self._ensure_doc_dirs(kb_id, doc.id)
            dest = _doc_raw_dir(kb_id, doc.id) / safe_name
            dest.write_bytes(data)
            rel = str(dest.relative_to(Path(settings.upload_dir)))
            doc.storage_path = rel
            job = await self.ingestion_job_service.create_job(kb.id, doc.id)
            doc_ids.append(doc.id)
            job_ids.append(job.id)

        await self.session.commit()

        # Refresh all documents to get updated fields
        docs = await self.doc_repo.list_for_kb(kb_id)
        uploaded = [d for d in docs if d.id in doc_ids]
        doc_reads: list[DocumentRead] = []
        for d in uploaded:
            doc_reads.append(await self._to_doc_read(d))

        from app.tasks.ingestion import process_batch_ingestion_task

        process_batch_ingestion_task.delay(
            str(self.user_id),
            str(kb.id),
            [str(did) for did in doc_ids],
            [str(jid) for jid in job_ids],
        )
        return BatchUploadResponse(created_count=len(doc_reads), documents=doc_reads)

    async def get_latest_ingestion_job(
        self, kb_id: uuid.UUID, doc_id: uuid.UUID
    ) -> IngestionJobRead:
        await self._require_kb(kb_id)
        doc = await self.doc_repo.get(kb_id, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        job = await self.ingestion_job_service.repo.get_latest_for_document(kb_id, doc_id)
        if job is None:
            raise HTTPException(status_code=404, detail="ingestion job not found")
        return IngestionJobRead.model_validate(job)

    async def get_replay_asset(
        self, kb_id: uuid.UUID, doc_id: uuid.UUID, asset_path: str
    ) -> FileResponse:
        await self._require_kb(kb_id)
        doc = await self.doc_repo.get(kb_id, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        self._check_replay_rate_limit(kb_id, doc_id)
        resolved = self._resolve_replay_asset_path(kb_id, doc_id, asset_path)
        if not resolved.is_file():
            raise HTTPException(status_code=404, detail="replay asset not found")
        size = resolved.stat().st_size
        if size > MAX_REPLAY_ASSET_BYTES:
            raise HTTPException(status_code=413, detail="replay asset too large")
        media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        return FileResponse(path=resolved, media_type=media_type, filename=resolved.name)

    async def retry_latest_ingestion_job(
        self, kb_id: uuid.UUID, doc_id: uuid.UUID
    ) -> IngestionJobRead:
        kb = await self._require_kb(kb_id)
        doc = await self.doc_repo.get(kb_id, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        latest = await self.ingestion_job_service.repo.get_latest_for_document(kb_id, doc_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="ingestion job not found")
        if latest.status not in ("failed", "queued"):
            raise HTTPException(status_code=409, detail="当前状态不可手动重试")

        if latest.status == "failed":
            latest = await self.ingestion_job_service.retry_job(latest.id)
        await self.session.commit()

        from app.tasks.ingestion import process_document_ingestion_task

        process_document_ingestion_task.delay(
            str(self.user_id),
            str(kb.id),
            str(doc.id),
            str(latest.id),
        )
        refreshed = await self.ingestion_job_service.repo.get(latest.id)
        if refreshed is None:
            raise HTTPException(status_code=404, detail="ingestion job not found")
        return IngestionJobRead.model_validate(refreshed)

    async def get_document_chunks(
        self,
        kb_id: uuid.UUID,
        doc_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 10,
        include_text: bool = True,
    ) -> DocumentChunksResponse:
        await self._require_kb(kb_id)
        doc = await self.doc_repo.get(kb_id, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        if doc.status != "completed":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "document_not_ready",
                    "message": "Document is not ready for chunk inspection",
                    "detail": {"document_id": str(doc.id), "status": doc.status},
                },
            )

        stats_result = await self.session.execute(
            select(
                func.count(KbVectorChunk.id),
                func.avg(func.length(KbVectorChunk.text)),
                func.min(func.length(KbVectorChunk.text)),
                func.max(func.length(KbVectorChunk.text)),
            ).where(
                KbVectorChunk.knowledge_base_id == kb_id,
                KbVectorChunk.document_id == doc_id,
            )
        )
        total_chunks, avg_char_length, min_char_length, max_char_length = stats_result.one()
        total = int(total_chunks or 0)
        total_pages = max(1, ceil(total / page_size)) if total > 0 else 1
        offset = (page - 1) * page_size

        rows = []
        try:
            if total > 0:
                rows_result = await self.session.execute(
                    select(KbVectorChunk)
                    .where(
                        KbVectorChunk.knowledge_base_id == kb_id,
                        KbVectorChunk.document_id == doc_id,
                    )
                    .order_by(KbVectorChunk.chunk_index.asc())
                    .offset(offset)
                    .limit(page_size)
                )
                rows = list(rows_result.scalars().all())
        except ProgrammingError as exc:
            msg = str(exc).lower()
            if "token_length" in msg or "source_metadata" in msg:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "数据库结构未升级到最新版本，请先执行 `alembic upgrade head` "
                        "后再访问分块详情。"
                    ),
                ) from exc
            raise

        items = [
            DocumentChunkRead(
                id=row.id,
                chunk_index=row.chunk_index,
                char_length=len(row.text),
                token_length=row.token_length,
                preview_text=row.text[:400] if include_text else None,
                source=_normalize_source_metadata(row.source_metadata),
                created_at=row.created_at,
            )
            for row in rows
        ]
        latest_job = await self.ingestion_job_service.repo.get_latest_for_document(kb_id, doc_id)
        return DocumentChunksResponse(
            document=DocumentChunkDocumentRead(
                id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                name=doc.file_name,
                status=doc.status,
                ingestion_job_id=latest_job.id if latest_job is not None else None,
                completed_at=doc.updated_at if doc.status == "completed" else None,
            ),
            chunk_summary=DocumentChunkSummaryRead(
                total_chunks=total,
                avg_char_length=float(avg_char_length) if avg_char_length is not None else None,
                min_char_length=int(min_char_length) if min_char_length is not None else None,
                max_char_length=int(max_char_length) if max_char_length is not None else None,
            ),
            pagination=DocumentChunkPaginationRead(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
            items=items,
        )

    async def process_document_ingestion(
        self,
        kb_id: uuid.UUID,
        doc_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> None:
        started_at = time.perf_counter()
        try:
            kb = await self._require_kb(kb_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                logger.warning(
                    "ingestion_job_dropped_missing_kb",
                    extra={"kb_id": str(kb_id), "doc_id": str(doc_id), "job_id": str(job_id)},
                )
                try:
                    await self.ingestion_job_service.fail_job(job_id, "knowledge base not found")
                    await self.session.commit()
                except Exception:
                    await self.session.rollback()
                return
            raise
        doc = await self.doc_repo.get(kb_id, doc_id)
        if doc is None:
            logger.warning(
                "ingestion_job_dropped_missing_doc",
                extra={"kb_id": str(kb_id), "doc_id": str(doc_id), "job_id": str(job_id)},
            )
            try:
                await self.ingestion_job_service.fail_job(job_id, "document not found")
                await self.session.commit()
            except Exception:
                await self.session.rollback()
            return
        await self.ingestion_job_service.start_processing(job_id)
        doc.status = "processing"
        doc.error_message = None
        await self.session.commit()
        if not doc.storage_path:
            await self.ingestion_job_service.fail_job(job_id, "缺少 storage_path，无法入库")
            doc.status = "failed"
            doc.error_message = "缺少 storage_path，无法入库"
            await self.notification_service.publish_ingestion_failed(
                kb_id=kb_id,
                doc_id=doc_id,
                job_id=job_id,
                doc_name=doc.file_name,
                error_message=doc.error_message,
            )
            await self.session.commit()
            return
        path = Path(settings.upload_dir) / doc.storage_path
        if not path.is_file():
            await self.ingestion_job_service.fail_job(job_id, "原文文件不存在")
            doc.status = "failed"
            doc.error_message = "原文文件不存在"
            await self.notification_service.publish_ingestion_failed(
                kb_id=kb_id,
                doc_id=doc_id,
                job_id=job_id,
                doc_name=doc.file_name,
                error_message=doc.error_message,
            )
            await self.session.commit()
            return
        data = path.read_bytes()
        await self._ingest_document(kb, doc, data)
        await self.session.refresh(doc)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        timed_out = elapsed_ms / 1000 >= settings.kb_ingestion_notification_timeout_seconds
        logger.info(
            "ingestion_job_finished",
            extra={
                "kb_id": str(kb_id),
                "doc_id": str(doc_id),
                "job_id": str(job_id),
                "status": doc.status,
                "elapsed_ms": elapsed_ms,
                "chunk_count": doc.chunk_count,
            },
        )
        if doc.status == "completed":
            if timed_out:
                await self.notification_service.publish_ingestion_timeout(
                    kb_id=kb_id, doc_id=doc_id, job_id=job_id, doc_name=doc.file_name
                )
            await self.notification_service.publish_ingestion_completed(
                kb_id=kb_id, doc_id=doc_id, job_id=job_id, doc_name=doc.file_name
            )
            await self.ingestion_job_service.complete_job(job_id)
            await self.session.commit()
            return
        if timed_out:
            await self.notification_service.publish_ingestion_timeout(
                kb_id=kb_id, doc_id=doc_id, job_id=job_id, doc_name=doc.file_name
            )
        await self.notification_service.publish_ingestion_failed(
            kb_id=kb_id,
            doc_id=doc_id,
            job_id=job_id,
            doc_name=doc.file_name,
            error_message=doc.error_message,
        )
        await self.ingestion_job_service.fail_job(job_id, doc.error_message or "文档入库失败")
        await self.session.commit()

    async def _ingest_document(self, kb: KnowledgeBase, doc: Document, file_bytes: bytes) -> None:
        if kb.embedding_model_id is None:
            raise HTTPException(status_code=500, detail="knowledge base missing embedding model")
        # Cache ids up-front to avoid any ORM lazy-load during error handling.
        kb_id = kb.id
        doc_id = doc.id
        vdbc = await self._get_vdbc(kb.vector_db_config_id)
        conn = vector_connector_for_config(vdbc, self.session)
        key = _collection_key(kb, vdbc.db_type)
        m = await self._get_embedding_model(kb.embedding_model_id)
        p = await self.provider_repo.get(m.provider_id)
        if p is None or not p.is_active:
            doc.status = "failed"
            doc.error_message = "provider 不可用"
            await self.session.commit()
            return
        doc.status = "processing"
        doc.error_message = None
        await self.session.commit()
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            blocks, parse_trace = self._build_blocks_from_segments(
                kb_id=kb.id,
                doc_id=doc.id,
                file_name=doc.file_name or "x.txt",
                file_bytes=file_bytes,
                retrieval_config=kb.retrieval_config,
            )
            blocks, ocr_status = await self._enrich_blocks_with_ocr(kb=kb, doc=doc, blocks=blocks)
            parse_trace["ocr_status"] = ocr_status
            if not blocks:
                doc.status = "failed"
                doc.chunk_count = 0
                doc.error_message = "文档解析未产出可用 blocks"
                await conn.delete_by_document(key, doc.id)
                await self.session.commit()
                return
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
            )
            chunks_with_source: list[tuple[str, dict]] = []
            for block in blocks:
                chunk_seed = self._build_multimodal_chunk_text(block)
                limit = kb.chunk_size if block.block_type != "text" else len(chunk_seed)
                split_source = chunk_seed[:limit]
                for chunk in splitter.split_text(split_source):
                    chunks_with_source.append(
                        (
                            chunk,
                            _build_source_metadata(
                                doc=doc,
                                block=block,
                                chunk_text=chunk,
                                parse_trace=parse_trace,
                            ),
                        )
                    )
            chunks = [chunk for chunk, _ in chunks_with_source]
            if not chunks:
                doc.status = "failed"
                doc.chunk_count = 0
                doc.error_message = "切块结果为空"
                await conn.delete_by_document(key, doc.id)
                await self.session.commit()
                return
            vectors = await embedding_client.embed_texts(
                provider_type=p.provider_type,
                api_key=p.api_key_encrypted,
                base_url=p.base_url,
                model_id=m.model_id,
                texts=chunks,
                batch_size=m.embedding_batch_size,
            )
            effective_base_url = p.base_url or "https://api.openai.com/v1"
            for vec in vectors:
                if len(vec) != kb.embedding_dimension:
                    raise embedding_client.EmbeddingError(
                        "向量维度不一致: "
                        f"provider 返回 {len(vec)} 维, "
                        f"知识库锁定 {kb.embedding_dimension} 维。"
                        f"(provider={p.provider_type}, "
                        f"model={m.model_id}, "
                        f"base_url={effective_base_url})。"
                        "请核对该 embedding 模型在平台登记的 "
                        "vector_dimension 是否与上游实际输出一致。"
                    )
            coll = kb.collection_name if vdbc.db_type == "qdrant" else str(kb.id)
            await conn.ensure_collection(coll, kb.embedding_dimension)

            items: list[VectorChunkItem] = []
            for i, ((chunk, source_meta), vec) in enumerate(
                zip(chunks_with_source, vectors, strict=True)
            ):
                h = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                items.append(
                    VectorChunkItem(
                        knowledge_base_id=kb.id,
                        document_id=doc.id,
                        chunk_index=i,
                        text=chunk,
                        embedding=vec,
                        content_hash=h,
                        token_length=_estimate_token_length(chunk),
                        source_metadata=source_meta,
                    )
                )
            await conn.delete_by_document(key, doc.id)
            await conn.upsert_chunks(key, items)
            doc.status = "completed"
            doc.chunk_count = len(items)
            doc.error_message = None
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            doc.status = "failed"
            # Keep user-facing error concise; log full details for debugging.
            logger.exception(
                "ingestion_failed",
                extra={
                    "kb_id": str(kb_id),
                    "doc_id": str(doc_id),
                    "error": _sanitize_error_message(str(e)),
                    "error_type": type(e).__name__,
                },
            )
            doc.error_message = _friendly_ingestion_error_message(e)
            await self.session.commit()

    async def delete_document(self, kb_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        kb = await self._require_kb(kb_id)
        doc = await self.doc_repo.get(kb_id, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        vdbc = await self._get_vdbc(kb.vector_db_config_id)
        conn = vector_connector_for_config(vdbc, self.session)
        key = _collection_key(kb, vdbc.db_type)
        try:
            await conn.delete_by_document(key, doc_id)
        except Exception as e:
            doc.error_message = f"向量清理失败: {e}"[:2000]
        self._cleanup_doc_all_assets(kb_id, doc_id)
        await self.doc_repo.soft_delete(doc)
        await self.session.commit()

    async def rebuild(self, kb_id: uuid.UUID, body: RebuildRequest) -> None:
        kb = await self._require_kb(kb_id)
        if body.document_id is not None:
            doc = await self.doc_repo.get(kb_id, body.document_id)
            if doc is None:
                raise HTTPException(status_code=404, detail="document not found")
            await self._rebuild_one(kb, doc)
            return
        docs = await self.doc_repo.list_for_kb(kb_id)
        for d in docs:
            if d.storage_path and d.deleted_at is None:
                await self._rebuild_one(kb, d)

    async def _rebuild_one(self, kb: KnowledgeBase, doc: Document) -> None:
        if not doc.storage_path:
            doc.status = "failed"
            doc.error_message = "缺少 storage_path，无法重建"
            await self.session.commit()
            return
        path = Path(settings.upload_dir) / doc.storage_path
        if not path.is_file():
            doc.status = "failed"
            doc.error_message = "原文文件不存在"
            await self.session.commit()
            return
        # Rebuild keeps original upload, clears derived assets for deterministic regeneration.
        self._cleanup_doc_derived_assets(kb.id, doc.id)
        data = path.read_bytes()
        await self._ingest_document(kb, doc, data)
        await self.session.refresh(doc)

    async def retrieve(self, kb_id: uuid.UUID, body: RetrieveRequest) -> RetrieveResponse:
        started_at = time.perf_counter()
        kb = await self._require_kb(kb_id)
        if kb.embedding_model_id is None:
            raise HTTPException(status_code=500, detail="knowledge base missing embedding model")
        vdbc = await self._get_vdbc(kb.vector_db_config_id)
        conn = vector_connector_for_config(vdbc, self.session)
        key = _collection_key(kb, vdbc.db_type)
        m = await self._get_embedding_model(kb.embedding_model_id)
        p = await self.provider_repo.get(m.provider_id)
        if p is None or not p.is_active:
            raise HTTPException(status_code=503, detail="provider 不可用")
        top_k = body.top_k if body.top_k is not None else kb.retrieval_top_k
        thr = (
            body.similarity_threshold
            if body.similarity_threshold is not None
            else kb.retrieval_similarity_threshold
        )
        strategy_id = body.strategy_id or "naive.v1"
        try:
            strategy = get_retrieval_strategy(strategy_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        qv = (
            await embedding_client.embed_texts(
                provider_type=p.provider_type,
                api_key=p.api_key_encrypted,
                base_url=p.base_url,
                model_id=m.model_id,
                texts=[body.query],
                batch_size=m.embedding_batch_size,
            )
        )[0]
        if len(qv) != kb.embedding_dimension:
            raise HTTPException(
                status_code=422,
                detail=(
                    "query 向量维度与知识库配置不一致: "
                    f"query={len(qv)}, kb={kb.embedding_dimension}"
                ),
            )
        try:
            hits = await strategy.retrieve(
                connector=conn,
                collection=key,
                knowledge_base_id=kb.id,
                query_vector=qv,
                top_k=top_k,
                similarity_threshold=thr,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "kb_retrieve_finished",
            extra={
                "kb_id": str(kb_id),
                "strategy_id": strategy.strategy_id,
                "top_k": top_k,
                "similarity_threshold": thr,
                "hits_count": len(hits),
                "elapsed_ms": elapsed_ms,
            },
        )
        return RetrieveResponse(
            strategy_id=strategy.strategy_id,
            retrieval_params={
                "top_k": top_k,
                "similarity_threshold": thr,
            },
            hits=[
                RetrieveHit(
                    knowledge_base_id=h.knowledge_base_id,
                    document_id=h.document_id,
                    chunk_index=h.chunk_index,
                    text=h.text,
                    score=h.score,
                    source=_normalize_source_metadata(h.source),
                )
                for h in hits
            ],
        )
