from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.infrastructure.llm_adapter import ResolvedModel
from app.models.model import Model
from app.models.provider import Provider
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.model_config import ModelConfigRepository


class DbModelConfigSource:
    """Read mode-level model config from DB with sensible fallbacks.

    Priority:
    - quick: knowledge_base_model_configs(purpose=llm) on first kb id
    - agent: agent_model_configs(agent_id=smart_agent)
    - fallback: first active llm model under current user providers
    """

    def __init__(self, *, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._cfg_repo = ModelConfigRepository(session, user_id)
        self._kb_repo = KnowledgeBaseRepository(session, user_id)

    async def get_llm_model_for_mode(
        self,
        *,
        user_id: uuid.UUID,
        mode: str,
        knowledge_base_ids: list[uuid.UUID] | None = None,
    ) -> ResolvedModel | None:
        # Safety: caller must pass same user scope as source initialization
        if user_id != self._user_id:
            return None

        if mode == "quick":
            resolved = await self._resolve_quick_model(knowledge_base_ids=knowledge_base_ids or [])
            if resolved is not None:
                return resolved
        elif mode == "agent":
            resolved = await self._resolve_agent_model(agent_id="smart_agent")
            if resolved is not None:
                return resolved

        return await self._resolve_fallback_model()

    async def _resolve_quick_model(self, *, knowledge_base_ids: list[uuid.UUID]) -> ResolvedModel | None:
        if not knowledge_base_ids:
            return None
        kb_id = knowledge_base_ids[0]
        kb = await self._kb_repo.get(kb_id)
        if kb is None:
            return None
        cfg = await self._cfg_repo.get_kb_config(kb.id, "llm")
        if cfg is None:
            return None
        model = await self._cfg_repo.get_model_scoped(cfg.model_id)
        if model is None or model.model_type != "llm":
            return None
        return await self._to_resolved_model(model)

    async def _resolve_agent_model(self, *, agent_id: str) -> ResolvedModel | None:
        cfg = await self._cfg_repo.get_agent_config(agent_id)
        if cfg is None:
            return None
        model = await self._cfg_repo.get_model_scoped(cfg.model_id)
        if model is None or model.model_type != "llm":
            return None
        return await self._to_resolved_model(model)

    async def _resolve_fallback_model(self) -> ResolvedModel | None:
        result = await self._session.execute(
            select(Model)
            .join(Provider, Model.provider_id == Provider.id)
            .where(
                Provider.user_id == self._user_id,
                Provider.deleted_at.is_(None),
                Provider.is_active.is_(True),
                Model.model_type == "llm",
            )
            .order_by(Model.created_at.asc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return await self._to_resolved_model(model)

    async def _to_resolved_model(self, model: Model) -> ResolvedModel | None:
        provider = await self._session.get(Provider, model.provider_id)
        if provider is None:
            return None
        return ResolvedModel(provider=provider.provider_type, model_name=model.model_id)
