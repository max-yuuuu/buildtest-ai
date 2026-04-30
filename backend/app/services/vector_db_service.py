import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vector_db_config import VectorDbConfig
from app.repositories.vector_db_config import VectorDbConfigRepository
from app.schemas.vector_db import (
    VectorDbCreate,
    VectorDbRead,
    VectorDbTestResult,
    VectorDbUpdate,
    mask_api_key_optional,
    mask_connection_string,
)
from app.services import vector_db_probe


class VectorDbService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repo = VectorDbConfigRepository(session, user_id)

    @staticmethod
    def _to_read(row: VectorDbConfig) -> VectorDbRead:
        return VectorDbRead(
            id=row.id,
            user_id=row.user_id,
            name=row.name,
            db_type=row.db_type,  # type: ignore[arg-type]
            connection_string_mask=row.connection_string_mask,
            api_key_mask=row.api_key_mask,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list(self) -> list[VectorDbRead]:
        items = await self.repo.list()
        return [self._to_read(r) for r in items]

    async def get(self, config_id: uuid.UUID) -> VectorDbRead:
        row = await self.repo.get(config_id)
        if row is None:
            raise HTTPException(status_code=404, detail="vector db config not found")
        return self._to_read(row)

    async def create(self, data: VectorDbCreate) -> VectorDbRead:
        api_mask = mask_api_key_optional(data.api_key) if data.api_key else None
        row = VectorDbConfig(
            name=data.name,
            db_type=data.db_type,
            connection_string=data.connection_string,
            connection_string_mask=mask_connection_string(data.connection_string),
            api_key_encrypted=data.api_key if data.api_key else None,
            api_key_mask=api_mask,
            is_active=data.is_active,
        )
        await self.repo.create(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_read(row)

    async def update(self, config_id: uuid.UUID, data: VectorDbUpdate) -> VectorDbRead:
        row = await self.repo.get(config_id)
        if row is None:
            raise HTTPException(status_code=404, detail="vector db config not found")
        if data.name is not None:
            row.name = data.name
        if data.connection_string is not None:
            row.connection_string = data.connection_string
            row.connection_string_mask = mask_connection_string(data.connection_string)
        if data.api_key is not None:
            if data.api_key == "":
                row.api_key_encrypted = None
                row.api_key_mask = None
            else:
                row.api_key_encrypted = data.api_key
                row.api_key_mask = mask_api_key_optional(data.api_key)
        if data.is_active is not None:
            row.is_active = data.is_active
        if row.is_active:
            await self.repo.deactivate_others(exclude_id=row.id)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_read(row)

    async def delete(self, config_id: uuid.UUID) -> None:
        row = await self.repo.get(config_id)
        if row is None:
            raise HTTPException(status_code=404, detail="vector db config not found")
        await self.repo.delete(row)
        await self.session.commit()

    async def test_connection(self, config_id: uuid.UUID) -> VectorDbTestResult:
        row = await self.repo.get(config_id)
        if row is None:
            raise HTTPException(status_code=404, detail="vector db config not found")
        api_plain = row.api_key_encrypted
        return await vector_db_probe.probe(row.db_type, row.connection_string, api_plain)

    async def test_active_connection(self) -> VectorDbTestResult:
        row = await self.repo.get_active()
        if row is None:
            raise HTTPException(status_code=404, detail="active vector db config not found")
        return await vector_db_probe.probe(
            row.db_type, row.connection_string, row.api_key_encrypted
        )
