import time
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider
from app.repositories.provider import ProviderRepository
from app.schemas.provider import (
    ProviderCreate,
    ProviderRead,
    ProviderTestResult,
    ProviderUpdate,
    mask_api_key,
)
from app.services import provider_probe


class ProviderService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repo = ProviderRepository(session, user_id)

    @staticmethod
    def _to_read(p: Provider) -> ProviderRead:
        return ProviderRead(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            provider_type=p.provider_type,  # type: ignore[arg-type]
            base_url=p.base_url,
            is_active=p.is_active,
            api_key_mask=p.api_key_mask,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    async def list(self) -> list[ProviderRead]:
        items = await self.repo.list()
        return [self._to_read(p) for p in items]

    async def get(self, provider_id: uuid.UUID) -> ProviderRead:
        p = await self.repo.get(provider_id)
        if p is None:
            raise HTTPException(status_code=404, detail="provider not found")
        return self._to_read(p)

    async def create(self, data: ProviderCreate) -> ProviderRead:
        provider = Provider(
            name=data.name,
            provider_type=data.provider_type,
            api_key_encrypted=data.api_key,  # EncryptedString 在落库时自动加密
            api_key_mask=mask_api_key(data.api_key),
            base_url=data.base_url,
            is_active=data.is_active,
        )
        await self.repo.create(provider)
        await self.session.commit()
        await self.session.refresh(provider)
        return self._to_read(provider)

    async def update(self, provider_id: uuid.UUID, data: ProviderUpdate) -> ProviderRead:
        p = await self.repo.get(provider_id)
        if p is None:
            raise HTTPException(status_code=404, detail="provider not found")
        if data.name is not None:
            p.name = data.name
        if data.api_key is not None:
            p.api_key_encrypted = data.api_key
            p.api_key_mask = mask_api_key(data.api_key)
        if data.base_url is not None:
            p.base_url = data.base_url
        if data.is_active is not None:
            p.is_active = data.is_active
        await self.session.commit()
        await self.session.refresh(p)
        return self._to_read(p)

    async def delete(self, provider_id: uuid.UUID) -> None:
        p = await self.repo.get(provider_id)
        if p is None:
            raise HTTPException(status_code=404, detail="provider not found")
        refs = await self.repo.count_models_referencing(provider_id)
        if refs > 0:
            raise HTTPException(
                status_code=409,
                detail=f"provider is referenced by {refs} model(s); remove them first",
            )
        await self.repo.delete(p)
        await self.session.commit()

    async def test_connection(self, provider_id: uuid.UUID) -> ProviderTestResult:
        """上游连通性测试。测试失败返回 ok=False + 200,只有 provider 不存在才 4xx。"""
        p = await self.repo.get(provider_id)
        if p is None:
            raise HTTPException(status_code=404, detail="provider not found")
        started = time.perf_counter()
        try:
            models = await provider_probe.list_models(
                p.provider_type, p.api_key_encrypted, p.base_url
            )
        except provider_probe.ProbeError as e:
            elapsed = int((time.perf_counter() - started) * 1000)
            return ProviderTestResult(ok=False, latency_ms=elapsed, message=str(e), models=[])
        elapsed = int((time.perf_counter() - started) * 1000)
        return ProviderTestResult(ok=True, latency_ms=elapsed, message="ok", models=models[:10])
