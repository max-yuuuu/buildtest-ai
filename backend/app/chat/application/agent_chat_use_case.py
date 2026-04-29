from __future__ import annotations

import uuid

from app.chat.domain.models import QuickChatResult
from app.chat.domain.ports import AnswerGeneratorPort, KnowledgeRetrieverPort, ToolInvokerPort
from app.chat.graphs.agent_chat_graph import run_agent_graph


class RunAgentChatUseCase:
    def __init__(
        self,
        *,
        retriever: KnowledgeRetrieverPort,
        tool_invoker: ToolInvokerPort,
        answer_generator: AnswerGeneratorPort,
        max_iters: int = 3,
    ) -> None:
        self._retriever = retriever
        self._tool_invoker = tool_invoker
        self._answer_generator = answer_generator
        self._max_iters = max_iters

    async def execute(self, *, knowledge_base_ids: list[uuid.UUID], message: str) -> QuickChatResult:
        return await run_agent_graph(
            message=message,
            knowledge_base_ids=knowledge_base_ids,
            retriever=self._retriever,
            tool_invoker=self._tool_invoker,
            answer_generator=self._answer_generator,
            max_iters=self._max_iters,
        )

