import uuid

import pytest
from fastapi import HTTPException

from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService


def test_chat_request_defaults_mode_to_quick():
    body = ChatRequest(message="hello", knowledge_base_ids=[uuid.uuid4()])
    assert body.mode == "quick"


@pytest.mark.asyncio
async def test_chat_service_agent_mode_returns_answer():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]
    result = await service.run(ChatRequest(message="hello", mode="agent", knowledge_base_ids=[uuid.uuid4()]))
    assert result.mode == "agent"
    assert isinstance(result.answer, str)


@pytest.mark.asyncio
async def test_chat_service_rejects_data_mode():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as exc:
        await service.run(ChatRequest(message="hello", mode="data", knowledge_base_ids=[uuid.uuid4()]))
    assert exc.value.status_code == 501
    assert exc.value.detail["code"] == "MODE_NOT_IMPLEMENTED"
