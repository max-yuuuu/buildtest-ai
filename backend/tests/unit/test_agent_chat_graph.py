import uuid

import pytest

from app.chat.graphs.agent_chat_graph import run_agent_graph


@pytest.mark.asyncio
async def test_agent_graph_direct_answer_without_tool_call():
    result = await run_agent_graph(message="你好", knowledge_base_ids=[uuid.uuid4()])
    assert isinstance(result.answer, str)
    assert len(result.tool_calls) == 0


@pytest.mark.asyncio
async def test_agent_graph_uses_tool_call_for_retrieval_intent():
    result = await run_agent_graph(message="请检索这个知识库", knowledge_base_ids=[uuid.uuid4()])
    assert isinstance(result.answer, str)
    assert len(result.tool_calls) == 1
