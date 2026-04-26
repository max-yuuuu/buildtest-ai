"""向量库统一抽象：postgres_pgvector（原生 SQL 检索）与 Qdrant。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_vector_chunk import KbVectorChunk
from app.models.vector_db_config import VectorDbConfig


@dataclass
class VectorChunkItem:
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    embedding: list[float]
    content_hash: str
    token_length: int | None = None
    source_metadata: dict | None = None


@dataclass
class SearchHit:
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    score: float
    source: dict | None = None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class VectorDbConnector(Protocol):
    async def ensure_collection(
        self,
        name: str,
        vector_size: int,
        distance: Literal["cosine", "l2", "dot"] = "cosine",
    ) -> None: ...

    async def upsert_chunks(self, collection: str, items: list[VectorChunkItem]) -> None: ...

    async def delete_by_document(self, collection: str, document_id: uuid.UUID) -> None: ...

    async def delete_by_knowledge_base(
        self, collection: str, knowledge_base_id: uuid.UUID
    ) -> None: ...

    async def search(
        self,
        collection: str,
        knowledge_base_id: uuid.UUID,
        query_vector: list[float],
        top_k: int,
        score_threshold: float | None,
    ) -> list[SearchHit]: ...


class PostgresPgVectorConnector:
    """业务库单表 kb_vector_chunks；按 knowledge_base_id 强隔离。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_collection(
        self,
        name: str,
        vector_size: int,
        distance: Literal["cosine", "l2", "dot"] = "cosine",
    ) -> None:
        _ = (name, vector_size, distance)

    async def upsert_chunks(self, collection: str, items: list[VectorChunkItem]) -> None:
        _ = collection
        if not items:
            return
        expected_dim = len(items[0].embedding)
        for item in items:
            if len(item.embedding) != expected_dim:
                raise ValueError(
                    "向量维度不一致: 入库批次中存在不同长度的 embedding，"
                    f"期望 {expected_dim}，实际 {len(item.embedding)}。"
                )
        dialect_name = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect_name == "postgresql":
            dim_result = await self.session.execute(
                text(
                    """
                    SELECT vector_dims(embedding)
                    FROM kb_vector_chunks
                    WHERE knowledge_base_id = :kb_id
                    LIMIT 1
                    """
                ),
                {"kb_id": items[0].knowledge_base_id},
            )
            stored_dim = dim_result.scalar_one_or_none()
            if stored_dim is not None and int(stored_dim) != expected_dim:
                raise ValueError(
                    "向量维度不一致: 待写入向量维度与知识库现有分块维度不匹配，"
                    f"写入为 {expected_dim}，已存储为 {int(stored_dim)}。"
                )
        for it in items:
            row = KbVectorChunk(
                knowledge_base_id=it.knowledge_base_id,
                document_id=it.document_id,
                chunk_index=it.chunk_index,
                content_hash=it.content_hash,
                text=it.text,
                embedding=it.embedding,
                token_length=it.token_length,
                source_metadata=it.source_metadata or {},
            )
            self.session.add(row)
        await self.session.flush()

    async def delete_by_document(self, collection: str, document_id: uuid.UUID) -> None:
        kb_id = uuid.UUID(collection)
        await self.session.execute(
            delete(KbVectorChunk).where(
                KbVectorChunk.knowledge_base_id == kb_id,
                KbVectorChunk.document_id == document_id,
            )
        )
        await self.session.flush()

    async def delete_by_knowledge_base(self, collection: str, knowledge_base_id: uuid.UUID) -> None:
        _ = collection
        await self.session.execute(
            delete(KbVectorChunk).where(KbVectorChunk.knowledge_base_id == knowledge_base_id)
        )
        await self.session.flush()

    async def search(
        self,
        collection: str,
        knowledge_base_id: uuid.UUID,
        query_vector: list[float],
        top_k: int,
        score_threshold: float | None,
    ) -> list[SearchHit]:
        _ = collection
        if not query_vector:
            return []

        dialect_name = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect_name != "postgresql":
            result = await self.session.execute(
                select(KbVectorChunk).where(KbVectorChunk.knowledge_base_id == knowledge_base_id)
            )
            rows = list(result.scalars().all())
            scored: list[SearchHit] = []
            for row in rows:
                sim = cosine_similarity(query_vector, row.embedding)
                if score_threshold is not None and sim < score_threshold:
                    continue
                scored.append(
                    SearchHit(
                        knowledge_base_id=row.knowledge_base_id,
                        document_id=row.document_id,
                        chunk_index=row.chunk_index,
                        text=row.text,
                        score=sim,
                        source=row.source_metadata or {},
                    )
                )
            scored.sort(key=lambda h: h.score, reverse=True)
            return scored[:top_k]

        dim_result = await self.session.execute(
            text(
                """
                SELECT vector_dims(embedding)
                FROM kb_vector_chunks
                WHERE knowledge_base_id = :kb_id
                LIMIT 1
                """
            ),
            {"kb_id": knowledge_base_id},
        )
        stored_dim = dim_result.scalar_one_or_none()
        if stored_dim is not None and int(stored_dim) != len(query_vector):
            raise ValueError(
                "向量维度不一致: 查询向量维度与已存储分块维度不匹配，"
                f"查询为 {len(query_vector)}，已存储为 {int(stored_dim)}。"
            )

        query_vec_literal = "[" + ",".join(str(float(item)) for item in query_vector) + "]"
        result = await self.session.execute(
            text(
                """
                SELECT
                    knowledge_base_id,
                    document_id,
                    chunk_index,
                    text,
                    source_metadata,
                    1 - (embedding <=> CAST(:query_vec AS vector)) AS score
                FROM kb_vector_chunks
                WHERE knowledge_base_id = :kb_id
                  AND (
                    CAST(:score_threshold AS double precision) IS NULL
                    OR 1 - (embedding <=> CAST(:query_vec AS vector))
                        >= CAST(:score_threshold AS double precision)
                  )
                ORDER BY embedding <=> CAST(:query_vec AS vector)
                LIMIT :top_k
                """
            ),
            {
                "kb_id": knowledge_base_id,
                "query_vec": query_vec_literal,
                "score_threshold": score_threshold,
                "top_k": top_k,
            },
        )
        rows = result.mappings().all()
        return [
            SearchHit(
                knowledge_base_id=row["knowledge_base_id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                text=row["text"],
                score=float(row["score"]),
                source=row["source_metadata"] or {},
            )
            for row in rows
        ]


class QdrantConnector:
    def __init__(self, base_url: str, api_key: str | None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _client(self):
        from qdrant_client import AsyncQdrantClient

        return AsyncQdrantClient(url=self._base_url, api_key=self._api_key)

    async def ensure_collection(
        self,
        name: str,
        vector_size: int,
        distance: Literal["cosine", "l2", "dot"] = "cosine",
    ) -> None:
        from qdrant_client.http import models as qm

        dist = qm.Distance.COSINE
        if distance == "l2":
            dist = qm.Distance.EUCLID
        elif distance == "dot":
            dist = qm.Distance.DOT
        client = self._client()
        exists = await client.collection_exists(name)
        if not exists:
            await client.create_collection(
                collection_name=name,
                vectors_config=qm.VectorParams(size=vector_size, distance=dist),
            )

    async def upsert_chunks(self, collection: str, items: list[VectorChunkItem]) -> None:
        from qdrant_client.http import models as qm

        if not items:
            return
        client = self._client()
        points = []
        for it in items:
            pid = str(
                uuid.uuid5(
                    it.knowledge_base_id,
                    f"{it.document_id}:{it.chunk_index}:{it.content_hash}",
                )
            )
            points.append(
                qm.PointStruct(
                    id=pid,
                    vector=it.embedding,
                    payload={
                        "knowledge_base_id": str(it.knowledge_base_id),
                        "document_id": str(it.document_id),
                        "chunk_index": it.chunk_index,
                        "text": it.text,
                        "content_hash": it.content_hash,
                        "source": it.source_metadata or {},
                    },
                )
            )
        await client.upsert(collection_name=collection, points=points, wait=True)

    async def delete_by_document(self, collection: str, document_id: uuid.UUID) -> None:
        from qdrant_client.http import models as qm

        client = self._client()
        await client.delete(
            collection_name=collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="document_id",
                            match=qm.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def delete_by_knowledge_base(self, collection: str, knowledge_base_id: uuid.UUID) -> None:
        from qdrant_client.http import models as qm

        client = self._client()
        await client.delete(
            collection_name=collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="knowledge_base_id",
                            match=qm.MatchValue(value=str(knowledge_base_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def search(
        self,
        collection: str,
        knowledge_base_id: uuid.UUID,
        query_vector: list[float],
        top_k: int,
        score_threshold: float | None,
    ) -> list[SearchHit]:
        from qdrant_client.http import models as qm

        client = self._client()
        flt = qm.Filter(
            must=[
                qm.FieldCondition(
                    key="knowledge_base_id",
                    match=qm.MatchValue(value=str(knowledge_base_id)),
                )
            ]
        )
        res = await client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=flt,
            with_payload=True,
        )
        hits: list[SearchHit] = []
        for p in res:
            pl = p.payload or {}
            did = pl.get("document_id")
            if did is None:
                continue
            hits.append(
                SearchHit(
                    knowledge_base_id=knowledge_base_id,
                    document_id=uuid.UUID(str(did)),
                    chunk_index=int(pl.get("chunk_index", 0)),
                    text=str(pl.get("text", "")),
                    score=float(p.score),
                    source=pl.get("source"),
                )
            )
        return hits


def vector_connector_for_config(
    row: VectorDbConfig,
    session: AsyncSession,
) -> VectorDbConnector:
    if row.db_type == "postgres_pgvector":
        return PostgresPgVectorConnector(session)
    if row.db_type == "qdrant":
        return QdrantConnector(row.connection_string, row.api_key_encrypted)
    raise ValueError(f"unsupported vector db type: {row.db_type}")
