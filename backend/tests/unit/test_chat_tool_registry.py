import pytest
from fastapi import HTTPException

from app.services.chat_tool_registry import ToolRegistry


@pytest.mark.asyncio
async def test_tool_registry_returns_unified_contract():
    registry = ToolRegistry()

    async def handler(payload: dict) -> dict:
        return {"echo": payload["q"]}

    registry.register("api_retrieve", "api", handler)
    registry.set_mode_allowlist("quick", {"api_retrieve"})
    result = await registry.call(mode="quick", tool_id="api_retrieve", payload={"q": "hello"})

    assert result.tool_id == "api_retrieve"
    assert result.category == "api"
    assert result.input["q"] == "hello"
    assert result.result["echo"] == "hello"
    assert "mode" in result.trace_meta


@pytest.mark.asyncio
async def test_tool_registry_rejects_non_allowlisted_tool():
    registry = ToolRegistry()

    async def handler(payload: dict) -> dict:
        return payload

    registry.register("api_retrieve", "api", handler)
    registry.register("api_other", "api", handler)
    registry.set_mode_allowlist("quick", {"api_retrieve"})

    with pytest.raises(HTTPException) as exc:
        await registry.call(mode="quick", tool_id="api_other", payload={})

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "TOOL_NOT_ALLOWED"
