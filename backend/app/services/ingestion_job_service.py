import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_job import IngestionJob
from app.repositories.ingestion_job import IngestionJobRepository


class IngestionJobService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repo = IngestionJobRepository(session, user_id)

    async def create_job(
        self, kb_id: uuid.UUID, doc_id: uuid.UUID, max_retries: int = 3
    ) -> IngestionJob:
        job = IngestionJob(
            user_id=self.user_id,
            knowledge_base_id=kb_id,
            document_id=doc_id,
            status="queued",
            max_retries=max_retries,
        )
        await self.repo.create(job)
        return job

    async def start_processing(self, job_id: uuid.UUID) -> None:
        updated = await self.repo.mark_processing_if_queued(job_id)
        if not updated:
            raise HTTPException(status_code=409, detail="job 状态冲突，无法开始处理")

    async def complete_job(self, job_id: uuid.UUID) -> None:
        updated = await self.repo.mark_completed_if_processing(job_id)
        if not updated:
            raise HTTPException(status_code=409, detail="job 状态冲突，无法标记完成")

    async def fail_job(self, job_id: uuid.UUID, error_message: str) -> None:
        updated = await self.repo.mark_failed(job_id, error_message)
        if not updated:
            raise HTTPException(status_code=409, detail="job 状态冲突，无法标记失败")

    async def retry_job(self, job_id: uuid.UUID) -> IngestionJob:
        job = await self.repo.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="ingestion job not found")
        if job.status != "failed":
            raise HTTPException(status_code=409, detail="仅 failed 状态可重试")
        if job.attempt_count >= job.max_retries:
            raise HTTPException(status_code=409, detail="已达最大重试次数")
        updated = await self.repo.requeue_failed(job_id)
        if not updated:
            raise HTTPException(status_code=409, detail="job 状态冲突，无法重试入队")
        refreshed = await self.repo.get(job_id)
        if refreshed is None:
            raise HTTPException(status_code=404, detail="ingestion job not found")
        return refreshed
