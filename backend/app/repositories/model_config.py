import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.models.model_config import AgentModelConfig, KnowledgeBaseModelConfig
from app.models.provider import Provider


class ModelConfigRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def list_kb_configs(self, knowledge_base_id: uuid.UUID) -> Sequence[KnowledgeBaseModelConfig]:
        result = await self.session.execute(
            select(KnowledgeBaseModelConfig)
            .where(KnowledgeBaseModelConfig.knowledge_base_id == knowledge_base_id)
            .order_by(KnowledgeBaseModelConfig.purpose.asc())
        )
        return result.scalars().all()

    async def get_kb_config(
        self, knowledge_base_id: uuid.UUID, purpose: str
    ) -> KnowledgeBaseModelConfig | None:
        result = await self.session.execute(
            select(KnowledgeBaseModelConfig).where(
                KnowledgeBaseModelConfig.knowledge_base_id == knowledge_base_id,
                KnowledgeBaseModelConfig.purpose == purpose,
            )
        )
        return result.scalar_one_or_none()

    async def delete_kb_configs_except(self, knowledge_base_id: uuid.UUID, purposes: set[str]) -> None:
        stmt = delete(KnowledgeBaseModelConfig).where(
            KnowledgeBaseModelConfig.knowledge_base_id == knowledge_base_id
        )
        if purposes:
            stmt = stmt.where(KnowledgeBaseModelConfig.purpose.not_in(purposes))
        await self.session.execute(stmt)

    async def save_kb_config(self, config: KnowledgeBaseModelConfig) -> KnowledgeBaseModelConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def list_agent_configs(self) -> Sequence[AgentModelConfig]:
        result = await self.session.execute(
            select(AgentModelConfig)
            .where(AgentModelConfig.user_id == self.user_id)
            .order_by(AgentModelConfig.agent_id.asc())
        )
        return result.scalars().all()

    async def get_agent_config(self, agent_id: str) -> AgentModelConfig | None:
        result = await self.session.execute(
            select(AgentModelConfig).where(
                AgentModelConfig.user_id == self.user_id,
                AgentModelConfig.agent_id == agent_id,
            )
        )
        return result.scalar_one_or_none()

    async def save_agent_config(self, config: AgentModelConfig) -> AgentModelConfig:
        self.session.add(config)
        await self.session.flush()
        return config

    async def get_model_scoped(self, model_id: uuid.UUID) -> Model | None:
        result = await self.session.execute(
            select(Model)
            .join(Provider, Model.provider_id == Provider.id)
            .where(
                Model.id == model_id,
                Provider.user_id == self.user_id,
                Provider.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
