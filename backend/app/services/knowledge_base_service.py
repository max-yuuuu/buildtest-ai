from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from math import ceil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.kb_vector_chunk import KbVectorChunk
from app.models.knowledge_base import KnowledgeBase
from app.models.model import Model
from app.models.vector_db_config import VectorDbConfig
from app.repositories.document import DocumentRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.model import ModelRepository
from app.repositories.provider import ProviderRepository
from app.repositories.vector_db_config import VectorDbConfigRepository
from app.schemas.knowledge_base import (
    BatchUploadResponse,
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
)
from app.services import embedding_client
from app.services.document_loaders import extract_segments, infer_section_title
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
            retrieval_config=data.retrieval_config or {},
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
            kb.retrieval_config = data.retrieval_config
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
        base = Path(settings.upload_dir) / str(kb_id) / str(doc.id)
        base.mkdir(parents=True, exist_ok=True)
        dest = base / safe_name
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
            base = Path(settings.upload_dir) / str(kb_id) / str(doc.id)
            base.mkdir(parents=True, exist_ok=True)
            dest = base / safe_name
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
                source=row.source_metadata or {},
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
        kb = await self._require_kb(kb_id)
        doc = await self.doc_repo.get(kb_id, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
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

            segments = extract_segments(file_name=doc.file_name or "x.txt", data=file_bytes)
            if not segments:
                doc.status = "failed"
                doc.chunk_count = 0
                doc.error_message = "未抽取到文本内容，请确认文件不是扫描件或已损坏"
                await conn.delete_by_document(key, doc.id)
                await self.session.commit()
                return
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
            )
            chunks_with_source: list[tuple[str, dict]] = []
            for seg in segments:
                for chunk in splitter.split_text(seg.text):
                    chunks_with_source.append(
                        (
                            chunk,
                            {
                                "page": seg.page,
                                "section": infer_section_title(chunk),
                            },
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
            doc.status = "failed"
            doc.error_message = str(e)[:2000]
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
                    source=h.source,
                )
                for h in hits
            ],
        )
