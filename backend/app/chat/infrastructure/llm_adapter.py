from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    provider: str
    model_name: str


class ModelConfigSource(Protocol):
    async def get_llm_model_for_mode(self, *, user_id: uuid.UUID, mode: str) -> ResolvedModel | None: ...


class LLMAdapter:
    """mode 级 LLM 模型解析与兜底。

    MVP 目标：提供稳定的“读取 + fallback”入口；真实 LLM 调用在后续任务接入。
    """

    def __init__(self, *, config_source: ModelConfigSource, default_model: ResolvedModel | None = None) -> None:
        self._config_source = config_source
        self._default_model = default_model or ResolvedModel(provider="openai", model_name="default")

    async def resolve(self, *, mode: str, user_id: uuid.UUID) -> ResolvedModel:
        configured = await self._config_source.get_llm_model_for_mode(user_id=user_id, mode=mode)
        return configured or self._default_model

