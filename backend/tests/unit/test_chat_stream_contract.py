import uuid

import pytest

from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.quick_chat_workflow import QuickChatOutput, RetrievalAttempt


@pytest.mark.asyncio
async def test_chat_stream_event_order_and_single_done():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]

    async def fake_run_quick(body):  # noqa: ANN001
        _ = body
        return QuickChatOutput(
            answer="hello world",
            citations=[
                {
                    "citation_id": "c1",
                    "document_id": str(uuid.uuid4()),
                    "chunk_index": 0,
                    "score": 0.9,
                    "source": {"section": "doc"},
                }
            ],
            citation_mappings=[],
            attempts=[RetrievalAttempt(attempt=1, query="hello", hit_count=1, latency_ms=12)],
            tool_call=None,  # type: ignore[arg-type]
        )

    service._run_quick = fake_run_quick  # type: ignore[method-assign]
    events = [
        e
        async for e in service.stream(
            ChatRequest(message="hello", knowledge_base_id=uuid.uuid4(), mode="quick")
        )
    ]

    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"
    assert len([e for e in events if e["type"] == "done"]) == 1
    assert any(e["type"] == "token" for e in events)
    assert any(e["type"] == "citation" for e in events)


@pytest.mark.asyncio
async def test_chat_stream_terminates_on_error_without_done():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]

    async def fake_run_quick(_body):  # noqa: ANN001
        raise RuntimeError("boom")

    service._run_quick = fake_run_quick  # type: ignore[method-assign]
    events = [
        e
        async for e in service.stream(
            ChatRequest(message="hello", knowledge_base_id=uuid.uuid4(), mode="quick")
        )
    ]
    assert events[-1]["type"] == "error"
    assert not any(e["type"] == "done" for e in events)


@pytest.mark.asyncio
async def test_chat_stream_agent_mode_emits_error_event():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]
    events = [
        e
        async for e in service.stream(
            ChatRequest(message="hello", knowledge_base_id=uuid.uuid4(), mode="agent")
        )
    ]
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["code"] == "MODE_NOT_IMPLEMENTED"
