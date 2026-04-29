from __future__ import annotations

import uuid

from app.chat.domain.errors import ModeNotImplementedError
from app.chat.domain.models import QuickChatResult


class RunDataChatUseCase:
    async def execute(self, *, knowledge_base_ids: list[uuid.UUID], message: str) -> QuickChatResult:
        _ = (knowledge_base_ids, message)
        raise ModeNotImplementedError("data")

