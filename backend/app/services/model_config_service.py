import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_config import AgentModelConfig, KnowledgeBaseModelConfig
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.model_config import ModelConfigRepository
from app.schemas.model_config import (
    AgentModelConfigRead,
    AgentModelConfigUpsert,
    KnowledgeBaseModelConfigRead,
    KnowledgeBaseModelConfigUpsert,
)

_PURPOSE_TO_MODEL_TYPE = {
    "embedding": "embedding",
    "llm": "llm",
    "rerank": "rerank",
    "vlm": "vlm",
}


class ModelConfigService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.kb_repo = KnowledgeBaseRepository(session, user_id)
        self.repo = ModelConfigRepository(session, user_id)

    @staticmethod
    def _to_kb_read(row: KnowledgeBaseModelConfig) -> KnowledgeBaseModelConfigRead:
        return KnowledgeBaseModelConfigRead(
            id=row.id,
            knowledge_base_id=row.knowledge_base_id,
            purpose=row.purpose,  # type: ignore[arg-type]
            model_id=row.model_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_agent_read(row: AgentModelConfig) -> AgentModelConfigRead:
        return AgentModelConfigRead(
            id=row.id,
            user_id=row.user_id,
            agent_id=row.agent_id,
            model_id=row.model_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_kb_configs(self, knowledge_base_id: uuid.UUID) -> list[KnowledgeBaseModelConfigRead]:
        kb = await self.kb_repo.get(knowledge_base_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="knowledge base not found")

        rows = list(await self.repo.list_kb_configs(knowledge_base_id))
        # Legacy fallback: if config table missing embedding but KB has embedding_model_id, expose it.
        if kb.embedding_model_id and not any(r.purpose == "embedding" for r in rows):
            rows.append(
                KnowledgeBaseModelConfig(
                    knowledge_base_id=knowledge_base_id,
                    purpose="embedding",
                    model_id=kb.embedding_model_id,
                )
            )
        rows.sort(key=lambda x: x.purpose)
        return [self._to_kb_read(row) for row in rows]

    async def put_kb_configs(
        self, knowledge_base_id: uuid.UUID, payload: list[KnowledgeBaseModelConfigUpsert]
    ) -> list[KnowledgeBaseModelConfigRead]:
        kb = await self.kb_repo.get(knowledge_base_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="knowledge base not found")

        seen_purposes: set[str] = set()
        for item in payload:
            if item.purpose in seen_purposes:
                raise HTTPException(status_code=422, detail=f"duplicated purpose: {item.purpose}")
            seen_purposes.add(item.purpose)
            model = await self.repo.get_model_scoped(item.model_id)
            if model is None:
                raise HTTPException(status_code=404, detail=f"model not found for purpose: {item.purpose}")
            expected_type = _PURPOSE_TO_MODEL_TYPE[item.purpose]
            if model.model_type != expected_type:
                raise HTTPException(
                    status_code=422,
                    detail=f"purpose {item.purpose} requires model_type={expected_type}",
                )

        await self.repo.delete_kb_configs_except(knowledge_base_id, seen_purposes)
        for item in payload:
            existing = await self.repo.get_kb_config(knowledge_base_id, item.purpose)
            if existing is None:
                existing = KnowledgeBaseModelConfig(
                    knowledge_base_id=knowledge_base_id,
                    purpose=item.purpose,
                    model_id=item.model_id,
                )
            else:
                existing.model_id = item.model_id
            await self.repo.save_kb_config(existing)

        await self.session.commit()
        return await self.list_kb_configs(knowledge_base_id)

    async def list_agent_configs(self) -> list[AgentModelConfigRead]:
        rows = await self.repo.list_agent_configs()
        return [self._to_agent_read(row) for row in rows]

    async def upsert_agent_config(self, agent_id: str, payload: AgentModelConfigUpsert) -> AgentModelConfigRead:
        model = await self.repo.get_model_scoped(payload.model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="model not found")
        if model.model_type != "llm":
            raise HTTPException(status_code=422, detail="agent model must be llm type")

        row = await self.repo.get_agent_config(agent_id)
        if row is None:
            row = AgentModelConfig(user_id=self.user_id, agent_id=agent_id, model_id=payload.model_id)
        else:
            row.model_id = payload.model_id
        await self.repo.save_agent_config(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_agent_read(row)
