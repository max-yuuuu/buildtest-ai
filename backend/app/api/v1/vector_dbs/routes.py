import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.schemas.vector_db import VectorDbCreate, VectorDbRead, VectorDbTestResult, VectorDbUpdate
from app.services.vector_db_service import VectorDbService

router = APIRouter()


@router.get("", response_model=list[VectorDbRead])
async def list_vector_dbs(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[VectorDbRead]:
    return await VectorDbService(session, user_id).list()


@router.post("", response_model=VectorDbRead, status_code=status.HTTP_201_CREATED)
async def create_vector_db(
    data: VectorDbCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> VectorDbRead:
    return await VectorDbService(session, user_id).create(data)


@router.get("/{config_id}", response_model=VectorDbRead)
async def get_vector_db(
    config_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> VectorDbRead:
    return await VectorDbService(session, user_id).get(config_id)


@router.put("/{config_id}", response_model=VectorDbRead)
async def update_vector_db(
    config_id: uuid.UUID,
    data: VectorDbUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> VectorDbRead:
    return await VectorDbService(session, user_id).update(config_id, data)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vector_db(
    config_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    await VectorDbService(session, user_id).delete(config_id)


@router.post("/{config_id}/test", response_model=VectorDbTestResult)
async def test_vector_db(
    config_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> VectorDbTestResult:
    return await VectorDbService(session, user_id).test_connection(config_id)


@router.get("/active/probe", response_model=VectorDbTestResult)
async def test_active_vector_db(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> VectorDbTestResult:
    return await VectorDbService(session, user_id).test_active_connection()
