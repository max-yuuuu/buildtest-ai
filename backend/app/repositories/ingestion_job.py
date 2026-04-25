import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_job import IngestionJob


class IngestionJobRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _scoped(self):
        return select(IngestionJob).where(IngestionJob.user_id == self.user_id)

    async def create(self, row: IngestionJob) -> IngestionJob:
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, job_id: uuid.UUID) -> IngestionJob | None:
        r = await self.session.execute(self._scoped().where(IngestionJob.id == job_id))
        return r.scalar_one_or_none()

    async def get_latest_for_document(
        self, kb_id: uuid.UUID, doc_id: uuid.UUID
    ) -> IngestionJob | None:
        r = await self.session.execute(
            self._scoped()
            .where(
                IngestionJob.knowledge_base_id == kb_id,
                IngestionJob.document_id == doc_id,
            )
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        return r.scalar_one_or_none()

    async def list_for_document(
        self, kb_id: uuid.UUID, doc_id: uuid.UUID
    ) -> Sequence[IngestionJob]:
        r = await self.session.execute(
            self._scoped()
            .where(
                IngestionJob.knowledge_base_id == kb_id,
                IngestionJob.document_id == doc_id,
            )
            .order_by(IngestionJob.created_at.desc())
        )
        return r.scalars().all()

    async def mark_processing_if_queued(self, job_id: uuid.UUID) -> bool:
        stmt = (
            update(IngestionJob)
            .where(
                IngestionJob.id == job_id,
                IngestionJob.status == "queued",
                IngestionJob.user_id == self.user_id,
            )
            .values(
                status="processing",
                started_at=datetime.now(UTC),
                error_message=None,
                attempt_count=IngestionJob.attempt_count + 1,
            )
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)

    async def mark_completed_if_processing(self, job_id: uuid.UUID) -> bool:
        stmt = (
            update(IngestionJob)
            .where(
                IngestionJob.id == job_id,
                IngestionJob.status == "processing",
                IngestionJob.user_id == self.user_id,
            )
            .values(
                status="completed",
                finished_at=datetime.now(UTC),
                error_message=None,
            )
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)

    async def mark_failed(self, job_id: uuid.UUID, error_message: str) -> bool:
        stmt = (
            update(IngestionJob)
            .where(
                IngestionJob.id == job_id,
                IngestionJob.status.in_(("queued", "processing")),
                IngestionJob.user_id == self.user_id,
            )
            .values(
                status="failed",
                finished_at=datetime.now(UTC),
                error_message=error_message[:2000],
            )
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)

    async def requeue_failed(self, job_id: uuid.UUID) -> bool:
        stmt = (
            update(IngestionJob)
            .where(
                IngestionJob.id == job_id,
                IngestionJob.status == "failed",
                IngestionJob.user_id == self.user_id,
            )
            .values(
                status="queued",
                queued_at=datetime.now(UTC),
                started_at=None,
                finished_at=None,
                error_message=None,
            )
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)
