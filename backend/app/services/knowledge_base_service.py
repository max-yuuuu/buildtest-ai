from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.model import Model
from app.models.vector_db_config import VectorDbConfig
from app.repositories.document import DocumentRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.model import ModelRepository
from app.repositories.provider import ProviderRepository
from app.repositories.vector_db_config import VectorDbConfigRepository
from app.schemas.knowledge_base import (
    DocumentRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
    RebuildRequest,
    RetrieveHit,
    RetrieveRequest,
    RetrieveResponse,
)
from app.services import embedding_client
from app.services.document_loaders import extract_text
from app.services.vector_connector import VectorChunkItem, vector_connector_for_config


def _collection_key(kb: KnowledgeBase, db_type: str) -> str:
    if db_type == "postgres_pgvector":
        return str(kb.id)
    return kb.collection_name


def _make_collection_name(kb_id: uuid.UUID, dim: int) -> str:
    return f"kb_{kb_id.hex}_{dim}"


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.kb_repo = KnowledgeBaseRepository(session, user_id)
        self.doc_repo = DocumentRepository(session, user_id)
        self.vdb_repo = VectorDbConfigRepository(session, user_id)
        self.model_repo = ModelRepository(session, user_id)
        self.provider_repo = ProviderRepository(session, user_id)

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
        return KnowledgeBaseRead(
            id=kb.id,
            user_id=kb.user_id,
            name=kb.name,
            description=kb.description,
            vector_db_config_id=kb.vector_db_config_id,
            collection_name=kb.collection_name,
            embedding_model_id=kb.embedding_model_id,
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

    @staticmethod
    def _to_doc_read(d: Document) -> DocumentRead:
        return DocumentRead.model_validate(d)

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
        return [self._to_doc_read(d) for d in docs]

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
            status="pending",
        )
        await self.doc_repo.create(doc)
        await self.session.flush()
        base = Path(settings.upload_dir) / str(kb_id) / str(doc.id)
        base.mkdir(parents=True, exist_ok=True)
        dest = base / safe_name
        dest.write_bytes(data)
        rel = str(dest.relative_to(Path(settings.upload_dir)))
        doc.storage_path = rel
        await self.session.commit()
        await self.session.refresh(doc)
        await self._ingest_document(kb, doc, data)
        await self.session.refresh(doc)
        return self._to_doc_read(doc)

    async def _ingest_document(self, kb: KnowledgeBase, doc: Document, file_bytes: bytes) -> None:
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

            text = extract_text(file_name=doc.file_name or "x.txt", data=file_bytes)
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
            )
            chunks = splitter.split_text(text) if text.strip() else []
            if not chunks:
                doc.status = "completed"
                doc.chunk_count = 0
                await conn.delete_by_document(key, doc.id)
                await self.session.commit()
                return
            vectors = await embedding_client.embed_texts(
                provider_type=p.provider_type,
                api_key=p.api_key_encrypted,
                base_url=p.base_url,
                model_id=m.model_id,
                texts=chunks,
            )
            for vec in vectors:
                if len(vec) != kb.embedding_dimension:
                    raise embedding_client.EmbeddingError(
                        f"向量维度 {len(vec)} 与知识库锁定维度 {kb.embedding_dimension} 不一致"
                    )
            coll = kb.collection_name if vdbc.db_type == "qdrant" else str(kb.id)
            await conn.ensure_collection(coll, kb.embedding_dimension)

            items: list[VectorChunkItem] = []
            for i, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True)):
                h = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                items.append(
                    VectorChunkItem(
                        knowledge_base_id=kb.id,
                        document_id=doc.id,
                        chunk_index=i,
                        text=chunk,
                        embedding=vec,
                        content_hash=h,
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
        kb = await self._require_kb(kb_id)
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
        qv = (
            await embedding_client.embed_texts(
                provider_type=p.provider_type,
                api_key=p.api_key_encrypted,
                base_url=p.base_url,
                model_id=m.model_id,
                texts=[body.query],
            )
        )[0]
        if len(qv) != kb.embedding_dimension:
            raise HTTPException(status_code=500, detail="query 向量维度与知识库不一致")
        hits = await conn.search(
            collection=key,
            knowledge_base_id=kb.id,
            query_vector=qv,
            top_k=top_k,
            score_threshold=thr,
        )
        return RetrieveResponse(
            hits=[
                RetrieveHit(
                    document_id=h.document_id,
                    chunk_index=h.chunk_index,
                    text=h.text,
                    score=h.score,
                )
                for h in hits
            ],
        )
