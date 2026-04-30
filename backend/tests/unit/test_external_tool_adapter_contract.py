import pytest

from app.chat.infrastructure.external_tool_adapter import MockExternalToolAdapter


@pytest.mark.asyncio
async def test_external_tool_adapter_contract():
    adapter = MockExternalToolAdapter()
    out = await adapter.call(tool_name="langflow.run", payload={"input": "hi"})
    assert out["ok"] is True
    assert out["tool_name"] == "langflow.run"
    assert out["payload"] == {"input": "hi"}
    assert "trace_id" in out

