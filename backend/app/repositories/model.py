import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.models.model import Model
from app.models.provider import Provider


class ModelRepository:
    """Model 本身无 user_id 列,借 Provider.user_id 强制多租户隔离。
    查询一律 join providers,否则攻击者可用他人 provider_id 越权读写。"""

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _scoped(self):
        return (
            select(Model)
            .join(Provider, Model.provider_id == Provider.id)
            .where(Provider.user_id == self.user_id, Provider.deleted_at.is_(None))
        )

    async def provider_belongs_to_user(self, provider_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Provider.id).where(
                Provider.id == provider_id,
                Provider.user_id == self.user_id,
                Provider.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_by_provider(self, provider_id: uuid.UUID) -> Sequence[Model]:
        result = await self.session.execute(
            self._scoped().where(Model.provider_id == provider_id).order_by(Model.created_at.desc())
        )
        return result.scalars().all()

    async def get(self, model_pk: uuid.UUID) -> Model | None:
        result = await self.session.execute(self._scoped().where(Model.id == model_pk))
        return result.scalar_one_or_none()

    async def get_by_model_id(self, provider_id: uuid.UUID, model_id: str) -> Model | None:
        result = await self.session.execute(
            self._scoped().where(
                Model.provider_id == provider_id,
                Model.model_id == model_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, model: Model) -> Model:
        self.session.add(model)
        await self.session.flush()
        return model

    async def delete(self, model: Model) -> None:
        await self.session.delete(model)
        await self.session.flush()

    async def list_knowledge_base_labels_using_embedding_model(
        self, model_pk: uuid.UUID
    ) -> list[str]:
        """与 FK 一致：凡 embedding_model_id 仍指向该模型的行(含软删未清空)均计入。"""
        result = await self.session.execute(
            select(KnowledgeBase.name, KnowledgeBase.deleted_at)
            .where(
                KnowledgeBase.user_id == self.user_id,
                KnowledgeBase.embedding_model_id == model_pk,
            )
            .order_by(KnowledgeBase.name.asc())
        )
        labels: list[str] = []
        for name, deleted_at in result.all():
            if deleted_at is None:
                labels.append(name)
            else:
                labels.append(f"{name}（已删除，仍占引用）")
        return labels
