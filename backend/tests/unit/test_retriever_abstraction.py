import uuid

import pytest

from app.chat.domain.retriever import VectorRetriever
from app.schemas.knowledge_base import RetrieveHit


class _FakeKbAdapter:
    async def retrieve(self, *, knowledge_base_id, query):  # noqa: ANN001
        _ = (knowledge_base_id, query)
        return [
            RetrieveHit(
                knowledge_base_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                text="ctx",
                score=0.9,
                source={"page": 1},
            )
        ], 12


@pytest.mark.asyncio
async def test_vector_retriever_protocol_returns_hits_and_latency():
    retriever = VectorRetriever(_FakeKbAdapter())
    hits, latency_ms = await retriever.retrieve(knowledge_base_id=uuid.uuid4(), query="postgres")
    assert isinstance(hits, list)
    assert len(hits) == 1
    assert isinstance(latency_ms, int)
