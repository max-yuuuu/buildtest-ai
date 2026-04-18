import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.schemas.provider import ProviderCreate, ProviderRead, ProviderTestResult, ProviderUpdate
from app.services.provider_service import ProviderService

router = APIRouter()


@router.get("", response_model=list[ProviderRead])
async def list_providers(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderRead]:
    return await ProviderService(session, user_id).list()


@router.post("", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: ProviderCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProviderRead:
    return await ProviderService(session, user_id).create(data)


@router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(
    provider_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProviderRead:
    return await ProviderService(session, user_id).get(provider_id)


@router.put("/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: uuid.UUID,
    data: ProviderUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProviderRead:
    return await ProviderService(session, user_id).update(provider_id, data)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    await ProviderService(session, user_id).delete(provider_id)


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(
    provider_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProviderTestResult:
    return await ProviderService(session, user_id).test_connection(provider_id)
