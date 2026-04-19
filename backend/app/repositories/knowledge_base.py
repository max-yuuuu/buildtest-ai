import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _base(self):
        return select(KnowledgeBase).where(
            KnowledgeBase.user_id == self.user_id,
            KnowledgeBase.deleted_at.is_(None),
        )

    async def list(self) -> Sequence[KnowledgeBase]:
        r = await self.session.execute(
            self._base().order_by(KnowledgeBase.created_at.desc()),
        )
        return r.scalars().all()

    async def get(self, kb_id: uuid.UUID) -> KnowledgeBase | None:
        r = await self.session.execute(self._base().where(KnowledgeBase.id == kb_id))
        return r.scalar_one_or_none()

    async def create(self, row: KnowledgeBase) -> KnowledgeBase:
        row.user_id = self.user_id
        self.session.add(row)
        await self.session.flush()
        return row

    async def save(self, row: KnowledgeBase) -> None:
        await self.session.flush()

    async def soft_delete(self, row: KnowledgeBase) -> None:
        from datetime import UTC, datetime

        row.deleted_at = datetime.now(UTC)
        await self.session.flush()
