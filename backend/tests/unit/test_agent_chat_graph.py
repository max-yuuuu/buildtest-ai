import uuid

import pytest

from app.chat.domain.models import ToolCallRecord
from app.chat.graphs.agent_chat_graph import run_agent_graph
from app.schemas.knowledge_base import RetrieveHit


class _FakeRetriever:
    def __init__(self, hits: list[RetrieveHit]) -> None:
        self._hits = hits

    async def retrieve(self, *, knowledge_base_id, query):  # noqa: ANN001
        _ = (knowledge_base_id, query)
        return self._hits, 5


class _FakeToolInvoker:
    async def invoke_retrieve_tool(self, *, mode, knowledge_base_id, query):  # noqa: ANN001
        _ = (mode, knowledge_base_id, query)
        return ToolCallRecord(
            tool_id="api_retrieve",
            category="api",
            input={"query": query},
            result={"ok": True},
            latency_ms=1,
            trace_meta={"tool_call_id": "tool_1"},
        )


class _FakeAnswerGenerator:
    def generate(self, *, question: str, context: str, has_hits: bool) -> str:  # noqa: FBT001
        return f"Q:{question}|H:{has_hits}|C:{len(context)}"


@pytest.mark.asyncio
async def test_agent_graph_calls_tool_then_finalizes():
    doc_id = uuid.uuid4()
    hits = [
        RetrieveHit(
            knowledge_base_id=uuid.uuid4(),
            document_id=doc_id,
            chunk_index=0,
            text="ctx",
            score=0.9,
            source={"page": 1},
        )
    ]

    result = await run_agent_graph(
        message="hello",
        knowledge_base_ids=[uuid.uuid4()],
        retriever=_FakeRetriever(hits),
        tool_invoker=_FakeToolInvoker(),
        answer_generator=_FakeAnswerGenerator(),
        max_iters=3,
    )
    assert "Q:hello" in result.answer
    assert len(result.tool_calls) == 1
    assert len(result.citations) == 1
