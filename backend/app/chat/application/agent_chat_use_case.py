from __future__ import annotations

import uuid

from app.chat.graphs.agent_chat_graph import run_agent_graph
from app.chat.domain.models import QuickChatResult


class RunAgentChatUseCase:
    async def execute(self, *, knowledge_base_ids: list[uuid.UUID], message: str) -> QuickChatResult:
        return await run_agent_graph(message=message, knowledge_base_ids=knowledge_base_ids)

