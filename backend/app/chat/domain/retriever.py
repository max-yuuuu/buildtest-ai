from __future__ import annotations

import uuid
from typing import Protocol

from app.schemas.knowledge_base import RetrieveHit


class Retriever(Protocol):
    async def retrieve(
        self, *, knowledge_base_id: uuid.UUID, query: str
    ) -> tuple[list[RetrieveHit], int]: ...


class VectorRetriever:
    def __init__(self, kb_retriever: Retriever) -> None:
        self._kb_retriever = kb_retriever

    async def retrieve(
        self, *, knowledge_base_id: uuid.UUID, query: str
    ) -> tuple[list[RetrieveHit], int]:
        return await self._kb_retriever.retrieve(knowledge_base_id=knowledge_base_id, query=query)
