import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vector_db_config import VectorDbConfig


class VectorDbConfigRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _base_stmt(self):
        return select(VectorDbConfig).where(
            VectorDbConfig.user_id == self.user_id,
            VectorDbConfig.deleted_at.is_(None),
        )

    async def list(self) -> Sequence[VectorDbConfig]:
        result = await self.session.execute(
            self._base_stmt().order_by(VectorDbConfig.created_at.desc())
        )
        return result.scalars().all()

    async def get(self, config_id: uuid.UUID) -> VectorDbConfig | None:
        result = await self.session.execute(self._base_stmt().where(VectorDbConfig.id == config_id))
        return result.scalar_one_or_none()

    async def create(self, row: VectorDbConfig) -> VectorDbConfig:
        row.user_id = self.user_id
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete(self, row: VectorDbConfig) -> None:
        from datetime import UTC, datetime

        row.deleted_at = datetime.now(UTC)
        await self.session.flush()
