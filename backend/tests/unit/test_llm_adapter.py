import uuid

import pytest

from app.chat.infrastructure.llm_adapter import LLMAdapter, ResolvedModel


class _FakeConfigSource:
    def __init__(self, resolved: ResolvedModel | None) -> None:
        self._resolved = resolved

    async def get_llm_model_for_mode(self, *, user_id, mode):  # noqa: ANN001
        _ = (user_id, mode)
        return self._resolved


@pytest.mark.asyncio
async def test_llm_adapter_fallback_to_default_model():
    adapter = LLMAdapter(config_source=_FakeConfigSource(None))
    model = await adapter.resolve(mode="quick", user_id=uuid.uuid4())
    assert model.provider == "openai"
    assert model.model_name == "default"


@pytest.mark.asyncio
async def test_llm_adapter_returns_configured_model_when_present():
    adapter = LLMAdapter(
        config_source=_FakeConfigSource(ResolvedModel(provider="anthropic", model_name="claude-3-7")),
    )
    model = await adapter.resolve(mode="agent", user_id=uuid.uuid4())
    assert model.provider == "anthropic"
    assert model.model_name == "claude-3-7"

