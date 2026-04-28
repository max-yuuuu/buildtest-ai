from __future__ import annotations

import uuid

from app.chat.domain.errors import ModeNotImplementedError
from app.chat.domain.models import QuickChatResult


class RunAgentChatUseCase:
    async def execute(self, *, knowledge_base_id: uuid.UUID, message: str) -> QuickChatResult:
        _ = (knowledge_base_id, message)
        raise ModeNotImplementedError("agent")

