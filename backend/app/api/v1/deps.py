import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.user import UserRepository
from app.schemas.user import UserUpsert


async def get_session() -> AsyncSession:
    async for s in get_db():
        yield s


async def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
    session: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    """BFF 在所有请求头注入 X-User-Id(NextAuth session.user.id = provider:sub)。
    本依赖负责 upsert 到 users 表并返回内部 UUID。"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="missing X-User-Id")

    repo = UserRepository(session)
    user = await repo.upsert(
        UserUpsert(
            external_id=x_user_id,
            email=x_user_email or f"{x_user_id}@placeholder.local",
            name=x_user_name,
            avatar_url=None,
        )
    )
    await session.commit()
    return user.id
