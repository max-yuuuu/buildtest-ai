from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.schemas.knowledge_base import RetrieveHit

from .models import ToolCallRecord


class KnowledgeRetrieverPort(ABC):
    @abstractmethod
    async def retrieve(
        self, *, knowledge_base_id: uuid.UUID, query: str
    ) -> tuple[list[RetrieveHit], int]: ...


class ToolInvokerPort(ABC):
    @abstractmethod
    async def invoke_retrieve_tool(
        self, *, mode: str, knowledge_base_id: uuid.UUID, query: str
    ) -> ToolCallRecord: ...


class AnswerGeneratorPort(ABC):
    @abstractmethod
    def generate(self, *, question: str, context: str, has_hits: bool) -> str: ...
