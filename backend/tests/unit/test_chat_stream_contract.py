import uuid

import pytest

from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.quick_chat_workflow import QuickChatOutput, RetrievalAttempt


@pytest.mark.asyncio
async def test_chat_stream_event_order_and_single_done():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]

    async def fake_stream_quick_graph_events(_body):  # noqa: ANN001
        yield {"type": "step", "name": "retrieve", "status": "running"}
        yield {"type": "step", "name": "retrieve", "status": "completed"}
        yield {"type": "step", "name": "generate", "status": "running"}
        yield {
            "type": "result",
            "result": QuickChatOutput(
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
                attempts=[
                    RetrievalAttempt(
                        knowledge_base_id=str(uuid.uuid4()),
                        attempt=1,
                        query="hello",
                        hit_count=1,
                        latency_ms=12,
                    )
                ],
                tool_calls=[],
                errors=[],
            ),
        }
        yield {"type": "step", "name": "generate", "status": "completed"}

    service._stream_quick_graph_events = fake_stream_quick_graph_events  # type: ignore[method-assign]
    events = [
        e
        async for e in service.stream(
            ChatRequest(message="hello", knowledge_base_ids=[uuid.uuid4()], mode="quick")
        )
    ]

    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"
    assert len([e for e in events if e["type"] == "done"]) == 1
    assert any(e["type"] == "text-delta" for e in events)
    assert any(e["type"] == "citation" for e in events)


@pytest.mark.asyncio
async def test_chat_stream_emits_done_after_error():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]

    async def fake_stream_quick_graph_events(_body):  # noqa: ANN001
        if False:
            yield {}
        raise RuntimeError("boom")

    service._stream_quick_graph_events = fake_stream_quick_graph_events  # type: ignore[method-assign]
    events = [
        e
        async for e in service.stream(
            ChatRequest(message="hello", knowledge_base_ids=[uuid.uuid4()], mode="quick")
        )
    ]
    assert events[-2]["type"] == "error"
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_chat_stream_agent_mode_emits_error_event():
    service = ChatService(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]

    async def fake_stream_agent_graph_events(_body):  # noqa: ANN001
        yield {"type": "step", "name": "think", "status": "running"}
        yield {"type": "step", "name": "think", "status": "completed"}
        yield {"type": "step", "name": "tool_call", "status": "running"}
        yield {"type": "step", "name": "tool_call", "status": "completed"}
        yield {
            "type": "result",
            "result": QuickChatOutput(
                answer="agent answer",
                citations=[],
                citation_mappings=[],
                attempts=[
                    RetrievalAttempt(
                        knowledge_base_id=str(uuid.uuid4()),
                        attempt=1,
                        query="hello",
                        hit_count=0,
                        latency_ms=10,
                    )
                ],
                tool_calls=[],
                errors=[],
            ),
        }

    service._stream_agent_graph_events = fake_stream_agent_graph_events  # type: ignore[method-assign]
    events = [
        e
        async for e in service.stream(
            ChatRequest(message="hello", knowledge_base_ids=[uuid.uuid4()], mode="agent")
        )
    ]
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "text-delta" for e in events)
