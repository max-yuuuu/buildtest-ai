import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


class DocumentRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _scoped(self):
        return (
            select(Document)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(
                KnowledgeBase.user_id == self.user_id,
                KnowledgeBase.deleted_at.is_(None),
                Document.deleted_at.is_(None),
            )
        )

    async def list_for_kb(self, kb_id: uuid.UUID) -> Sequence[Document]:
        r = await self.session.execute(
            self._scoped()
            .where(Document.knowledge_base_id == kb_id)
            .order_by(Document.created_at.desc()),
        )
        return r.scalars().all()

    async def count_for_kb(self, kb_id: uuid.UUID) -> int:
        r = await self.session.execute(
            select(func.count())
            .select_from(Document)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(
                KnowledgeBase.user_id == self.user_id,
                KnowledgeBase.id == kb_id,
                KnowledgeBase.deleted_at.is_(None),
                Document.deleted_at.is_(None),
            ),
        )
        return int(r.scalar_one() or 0)

    async def get(self, kb_id: uuid.UUID, doc_id: uuid.UUID) -> Document | None:
        r = await self.session.execute(
            self._scoped().where(
                Document.knowledge_base_id == kb_id,
                Document.id == doc_id,
            ),
        )
        return r.scalar_one_or_none()

    async def create(self, row: Document) -> Document:
        self.session.add(row)
        await self.session.flush()
        return row

    async def soft_delete(self, row: Document) -> None:
        from datetime import UTC, datetime

        row.deleted_at = datetime.now(UTC)
        await self.session.flush()
