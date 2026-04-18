from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.models.provider import Provider
from app.repositories.model import ModelRepository
from app.repositories.provider import ProviderRepository
from app.schemas.model import AvailableModel, ModelCreate, ModelRead, ModelUpdate
from app.services import provider_probe


class ModelService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repo = ModelRepository(session, user_id)
        self.provider_repo = ProviderRepository(session, user_id)

    @staticmethod
    def _to_read(m: Model) -> ModelRead:
        return ModelRead(
            id=m.id,
            provider_id=m.provider_id,
            model_id=m.model_id,
            model_type=m.model_type,  # type: ignore[arg-type]
            context_window=m.context_window,
            vector_dimension=m.vector_dimension,
            created_at=m.created_at,
        )

    async def _ensure_provider(self, provider_id: uuid.UUID) -> Provider:
        """provider 不属于当前用户或已软删 → 404(不泄漏是否存在)。"""
        p = await self.provider_repo.get(provider_id)
        if p is None:
            raise HTTPException(status_code=404, detail="provider not found")
        return p

    async def list(self, provider_id: uuid.UUID) -> list[ModelRead]:
        await self._ensure_provider(provider_id)
        items = await self.repo.list_by_provider(provider_id)
        return [self._to_read(m) for m in items]

    async def get(self, provider_id: uuid.UUID, model_pk: uuid.UUID) -> ModelRead:
        await self._ensure_provider(provider_id)
        m = await self.repo.get(model_pk)
        if m is None or m.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="model not found")
        return self._to_read(m)

    async def create(self, provider_id: uuid.UUID, data: ModelCreate) -> ModelRead:
        await self._ensure_provider(provider_id)
        existing = await self.repo.get_by_model_id(provider_id, data.model_id)
        if existing is not None:
            raise HTTPException(status_code=409, detail="model already registered")
        m = Model(
            provider_id=provider_id,
            model_id=data.model_id,
            model_type=data.model_type,
            context_window=data.context_window,
            vector_dimension=data.vector_dimension,
        )
        try:
            await self.repo.create(m)
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="model already registered") from e
        await self.session.refresh(m)
        return self._to_read(m)

    async def update(
        self, provider_id: uuid.UUID, model_pk: uuid.UUID, data: ModelUpdate
    ) -> ModelRead:
        await self._ensure_provider(provider_id)
        m = await self.repo.get(model_pk)
        if m is None or m.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="model not found")
        if data.model_type is not None:
            m.model_type = data.model_type
        if data.context_window is not None:
            m.context_window = data.context_window
        if data.vector_dimension is not None:
            m.vector_dimension = data.vector_dimension
        # embedding 仍需保证 vector_dimension:改为 embedding 时若无维度则拒绝
        if m.model_type == "embedding" and m.vector_dimension is None:
            await self.session.rollback()
            raise HTTPException(
                status_code=422, detail="vector_dimension is required for embedding models"
            )
        await self.session.commit()
        await self.session.refresh(m)
        return self._to_read(m)

    async def delete(self, provider_id: uuid.UUID, model_pk: uuid.UUID) -> None:
        await self._ensure_provider(provider_id)
        m = await self.repo.get(model_pk)
        if m is None or m.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="model not found")
        await self.repo.delete(m)
        await self.session.commit()

    async def list_available(self, provider_id: uuid.UUID) -> list[AvailableModel]:
        p = await self._ensure_provider(provider_id)
        registered = {m.model_id for m in await self.repo.list_by_provider(provider_id)}
        try:
            upstream = await provider_probe.list_models(
                p.provider_type, p.api_key_encrypted, p.base_url
            )
        except provider_probe.ProbeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        return [AvailableModel(model_id=mid, is_registered=mid in registered) for mid in upstream]
