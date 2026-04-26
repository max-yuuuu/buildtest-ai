"""向量库统一抽象：postgres_pgvector（JSON 存 embedding + 内存相似度）与 Qdrant。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy import delete, select
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
    document_id: uuid.UUID
    chunk_index: int
    text: str
    score: float


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
                    document_id=row.document_id,
                    chunk_index=row.chunk_index,
                    text=row.text,
                    score=sim,
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]


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
                    document_id=uuid.UUID(str(did)),
                    chunk_index=int(pl.get("chunk_index", 0)),
                    text=str(pl.get("text", "")),
                    score=float(p.score),
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
