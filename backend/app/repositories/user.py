import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpsert


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_external_id(self, external_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def upsert(self, data: UserUpsert) -> User:
        user = await self.get_by_external_id(data.external_id)
        if user is None:
            user = User(
                external_id=data.external_id,
                email=data.email,
                name=data.name,
                avatar_url=data.avatar_url,
            )
            self.session.add(user)
        else:
            user.email = data.email
            user.name = data.name
            user.avatar_url = data.avatar_url
        await self.session.flush()
        return user
