import uuid

import pytest
from sqlalchemy import Text, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.kb_vector_chunk import KbVectorChunk
from app.models.knowledge_base import KnowledgeBase
from app.models.model import Model
from app.models.provider import Provider
from app.models.user import User
from app.models.vector_db_config import VectorDbConfig
from app.services.vector_connector import (
    PostgresPgVectorConnector,
    VectorChunkItem,
    cosine_similarity,
    vector_connector_for_config,
)


def test_cosine_similarity():
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0], [2.0]) == pytest.approx(1.0)


def test_kb_vector_chunk_embedding_uses_vector_type_on_postgres():
    col_type = KbVectorChunk.__table__.c.embedding.type
    pg_impl = col_type.load_dialect_impl(postgresql.dialect())
    sqlite_impl = col_type.load_dialect_impl(sqlite.dialect())

    assert pg_impl.get_col_spec().lower() == "vector"
    assert isinstance(sqlite_impl, Text)


@pytest.mark.asyncio
async def test_postgres_connector_upsert_and_search(session: AsyncSession):
    uid = uuid.uuid4()
    user = User(id=uid, external_id="gh:u1", email="u1@x.com", name="U")
    session.add(user)
    pid = uuid.uuid4()
    session.add(
        Provider(
            id=pid,
            user_id=uid,
            name="p",
            provider_type="openai",
            api_key_encrypted="k",
            api_key_mask="***",
        )
    )
    mid = uuid.uuid4()
    session.add(
        Model(
            id=mid,
            provider_id=pid,
            model_id="text-embedding-3-small",
            model_type="embedding",
            vector_dimension=3,
        )
    )
    vid = uuid.uuid4()
    session.add(
        VectorDbConfig(
            id=vid,
            user_id=uid,
            name="v",
            db_type="postgres_pgvector",
            connection_string="postgresql://localhost/x",
            connection_string_mask="***",
        )
    )
    kb_id = uuid.uuid4()
    session.add(
        KnowledgeBase(
            id=kb_id,
            user_id=uid,
            name="KB",
            vector_db_config_id=vid,
            collection_name="kb_x_3",
            embedding_model_id=mid,
            embedding_dimension=3,
            chunk_size=512,
            chunk_overlap=50,
        )
    )
    doc_id = uuid.uuid4()
    session.add(
        Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            file_name="a.txt",
            status="completed",
        )
    )
    await session.commit()

    conn = PostgresPgVectorConnector(session)
    key = str(kb_id)
    await conn.upsert_chunks(
        key,
        [
            VectorChunkItem(
                knowledge_base_id=kb_id,
                document_id=doc_id,
                chunk_index=0,
                text="alpha",
                embedding=[1.0, 0.0, 0.0],
                content_hash="h1",
            ),
            VectorChunkItem(
                knowledge_base_id=kb_id,
                document_id=doc_id,
                chunk_index=1,
                text="beta",
                embedding=[0.0, 1.0, 0.0],
                content_hash="h2",
            ),
        ],
    )
    await session.commit()

    hits = await conn.search(
        collection=key,
        knowledge_base_id=kb_id,
        query_vector=[0.9, 0.1, 0.0],
        top_k=5,
        score_threshold=0.0,
    )
    assert len(hits) == 2
    assert hits[0].score >= hits[1].score

    await conn.delete_by_document(key, doc_id)
    await session.commit()
    r = await session.execute(select(KbVectorChunk).where(KbVectorChunk.document_id == doc_id))
    assert r.scalars().all() == []


def test_vector_connector_factory_requires_supported_type(session: AsyncSession):
    row = VectorDbConfig(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="m",
        db_type="milvus",
        connection_string="x",
        connection_string_mask="*",
    )
    with pytest.raises(ValueError, match="unsupported"):
        vector_connector_for_config(row, session)
