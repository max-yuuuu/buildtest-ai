import uuid

import pytest

from app.schemas.knowledge_base import RetrieveHit, RetrieveResponse
from app.services.chat_tool_registry import ToolRegistry
from app.services.quick_chat_workflow import QuickChatWorkflow, normalize_query_node


class _FakeKbService:
    def __init__(self, rounds: list[list[RetrieveHit]]) -> None:
        self._rounds = rounds
        self._idx = 0

    async def retrieve(self, kb_id, body):  # noqa: ANN001
        _ = (kb_id, body)
        hits = self._rounds[min(self._idx, len(self._rounds) - 1)]
        self._idx += 1
        return RetrieveResponse(hits=hits, strategy_id="naive.v1", retrieval_params={})


@pytest.mark.asyncio
async def test_quick_chat_retries_once_on_empty_results():
    doc_id = uuid.uuid4()
    second_hits = [
        RetrieveHit(
            knowledge_base_id=uuid.uuid4(),
            document_id=doc_id,
            chunk_index=0,
            text="retrieved context",
            score=0.88,
            source={"page": 1},
        )
    ]
    kb_service = _FakeKbService([[], second_hits])

    registry = ToolRegistry()

    async def tool(payload: dict) -> dict:
        return payload

    registry.register("api_retrieve", "api", tool)
    registry.set_mode_allowlist("quick", {"api_retrieve"})
    workflow = QuickChatWorkflow(kb_service=kb_service, tool_registry=registry)

    out = await workflow.run(knowledge_base_id=uuid.uuid4(), message="  hello   world ")
    assert len(out.attempts) == 2
    assert out.attempts[0].hit_count == 0
    assert out.attempts[1].hit_count == 1
    assert "基于检索结果回答" in out.answer
    assert out.citations[0]["document_id"] == str(doc_id)


@pytest.mark.asyncio
async def test_quick_chat_fallback_when_both_attempts_empty():
    kb_service = _FakeKbService([[], []])
    registry = ToolRegistry()

    async def tool(payload: dict) -> dict:
        return payload

    registry.register("api_retrieve", "api", tool)
    registry.set_mode_allowlist("quick", {"api_retrieve"})
    workflow = QuickChatWorkflow(kb_service=kb_service, tool_registry=registry)

    out = await workflow.run(knowledge_base_id=uuid.uuid4(), message="unknown")
    assert len(out.attempts) == 2
    assert "可能不准确" in out.answer
    assert out.citations == []


def test_normalize_query_node():
    assert normalize_query_node(" a   b \n c ") == "a b c"
