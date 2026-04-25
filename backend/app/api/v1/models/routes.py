import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.schemas.model import (
    AvailableModel,
    EmbeddingDimensionProbeRequest,
    EmbeddingDimensionProbeResponse,
    ModelCreate,
    ModelRead,
    ModelUpdate,
)
from app.services.model_service import ModelService

router = APIRouter()


@router.get("", response_model=list[ModelRead])
async def list_models(
    provider_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ModelRead]:
    return await ModelService(session, user_id).list(provider_id)


@router.post("", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
async def create_model(
    provider_id: uuid.UUID,
    data: ModelCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ModelRead:
    return await ModelService(session, user_id).create(provider_id, data)


@router.get("/available", response_model=list[AvailableModel])
async def list_available_models(
    provider_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[AvailableModel]:
    return await ModelService(session, user_id).list_available(provider_id)


@router.get("/{model_pk}", response_model=ModelRead)
async def get_model(
    provider_id: uuid.UUID,
    model_pk: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ModelRead:
    return await ModelService(session, user_id).get(provider_id, model_pk)


@router.put("/{model_pk}", response_model=ModelRead)
async def update_model(
    provider_id: uuid.UUID,
    model_pk: uuid.UUID,
    data: ModelUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ModelRead:
    return await ModelService(session, user_id).update(provider_id, model_pk, data)


@router.post("/dimension-probe", response_model=EmbeddingDimensionProbeResponse)
async def probe_embedding_dimension(
    provider_id: uuid.UUID,
    data: EmbeddingDimensionProbeRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> EmbeddingDimensionProbeResponse:
    dim = await ModelService(session, user_id).probe_embedding_dimension(provider_id, data.model_id)
    return EmbeddingDimensionProbeResponse(model_id=data.model_id, vector_dimension=dim)


@router.delete("/{model_pk}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    provider_id: uuid.UUID,
    model_pk: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    await ModelService(session, user_id).delete(provider_id, model_pk)
