from __future__ import annotations

import uuid

from app.chat.application.agent_chat_use_case import RunAgentChatUseCase
from app.chat.application.data_chat_use_case import RunDataChatUseCase
from app.chat.application.quick_chat_use_case import RunQuickChatUseCase
from app.chat.domain.models import QuickChatResult
from app.chat.infrastructure.adapters import (
    KnowledgeBaseRetrieverAdapter,
    QuickModeToolInvokerAdapter,
    TemplateAnswerGeneratorAdapter,
)
from app.services.chat_tool_registry import ToolRegistry
from app.services.knowledge_base_service import KnowledgeBaseService


class ChatFacade:
    def __init__(self, kb_service: KnowledgeBaseService, tool_registry: ToolRegistry) -> None:
        self._quick_use_case = RunQuickChatUseCase(
            retriever=KnowledgeBaseRetrieverAdapter(kb_service),
            tool_invoker=QuickModeToolInvokerAdapter(tool_registry),
            answer_generator=TemplateAnswerGeneratorAdapter(),
            mode="quick",
        )
        self._agent_use_case = RunAgentChatUseCase()
        self._data_use_case = RunDataChatUseCase()

    async def run_quick(self, *, knowledge_base_id: uuid.UUID, message: str) -> QuickChatResult:
        return await self._quick_use_case.execute(knowledge_base_id=knowledge_base_id, message=message)

    async def run_agent(self, *, knowledge_base_id: uuid.UUID, message: str) -> QuickChatResult:
        return await self._agent_use_case.execute(knowledge_base_id=knowledge_base_id, message=message)

    async def run_data(self, *, knowledge_base_id: uuid.UUID, message: str) -> QuickChatResult:
        return await self._data_use_case.execute(knowledge_base_id=knowledge_base_id, message=message)
