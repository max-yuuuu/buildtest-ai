import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.repositories.user import UserRepository
from app.schemas.user import UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    assert user is not None
    return UserRead.model_validate(user)
