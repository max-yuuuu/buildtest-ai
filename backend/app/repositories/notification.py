import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _scoped(self):
        return select(Notification).where(Notification.user_id == self.user_id)

    async def list_paginated(
        self, *, page: int, page_size: int, unread_only: bool = False
    ) -> tuple[list[Notification], int]:
        base = self._scoped()
        if unread_only:
            base = base.where(Notification.is_read.is_(False))
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        result = await self.session.execute(
            base.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def unread_count(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == self.user_id, Notification.is_read.is_(False))
        )
        return int(result.scalar_one() or 0)

    async def mark_read(self, notification_ids: list[uuid.UUID]) -> int:
        if not notification_ids:
            return 0
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == self.user_id,
                Notification.id.in_(notification_ids),
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=datetime.now(UTC))
        )
        return int(result.rowcount or 0)

    async def create_if_absent(self, payload: dict[str, Any]) -> Notification | None:
        row = Notification(**payload)
        try:
            async with self.session.begin_nested():
                self.session.add(row)
                await self.session.flush()
                return row
        except IntegrityError:
            return None
