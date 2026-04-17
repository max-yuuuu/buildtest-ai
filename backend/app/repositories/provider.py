import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider


class ProviderRepository:
    """Repository 层统一注入 user_id 过滤,保证多租户隔离。"""

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _base_stmt(self):
        return select(Provider).where(
            Provider.user_id == self.user_id,
            Provider.deleted_at.is_(None),
        )

    async def list(self) -> Sequence[Provider]:
        result = await self.session.execute(self._base_stmt().order_by(Provider.created_at.desc()))
        return result.scalars().all()

    async def get(self, provider_id: uuid.UUID) -> Provider | None:
        result = await self.session.execute(
            self._base_stmt().where(Provider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def create(self, provider: Provider) -> Provider:
        provider.user_id = self.user_id
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def delete(self, provider: Provider) -> None:
        from datetime import UTC, datetime

        provider.deleted_at = datetime.now(UTC)
        await self.session.flush()
