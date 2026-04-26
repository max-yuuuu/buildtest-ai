import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationListResponse, NotificationRead

TIMEOUT_WINDOW_SECONDS = 30 * 60


class NotificationService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.repo = NotificationRepository(session, user_id)

    async def list_notifications(
        self, *, page: int, page_size: int, unread_only: bool = False
    ) -> NotificationListResponse:
        items, total = await self.repo.list_paginated(
            page=page, page_size=page_size, unread_only=unread_only
        )
        return NotificationListResponse(
            page=page,
            page_size=page_size,
            total=total,
            items=[NotificationRead.model_validate(item) for item in items],
        )

    async def unread_count(self) -> int:
        return await self.repo.unread_count()

    async def mark_read(self, notification_ids: list[uuid.UUID]) -> int:
        return await self.repo.mark_read(notification_ids)

    async def publish_ingestion_completed(
        self, *, kb_id: uuid.UUID, doc_id: uuid.UUID, job_id: uuid.UUID, doc_name: str
    ) -> None:
        dedupe_key = f"ingestion_completed:{job_id}"
        await self.repo.create_if_absent(
            {
                "user_id": self.user_id,
                "event_type": "ingestion_completed",
                "level": "success",
                "title": "文档处理完成",
                "message": f"《{doc_name}》处理完成，可开始检索",
                "resource_id": doc_id,
                "knowledge_base_id": kb_id,
                "ingestion_job_id": job_id,
                "action_url": f"/knowledge-bases/{kb_id}/documents/{doc_id}/chunks",
                "dedupe_key": dedupe_key,
            }
        )

    async def publish_ingestion_failed(
        self,
        *,
        kb_id: uuid.UUID,
        doc_id: uuid.UUID,
        job_id: uuid.UUID,
        doc_name: str,
        error_message: str | None = None,
    ) -> None:
        dedupe_key = f"ingestion_failed:{job_id}"
        suffix = f"（{error_message[:80]}）" if error_message else ""
        await self.repo.create_if_absent(
            {
                "user_id": self.user_id,
                "event_type": "ingestion_failed",
                "level": "error",
                "title": "文档处理失败",
                "message": f"《{doc_name}》处理失败，点击查看原因{suffix}",
                "resource_id": doc_id,
                "knowledge_base_id": kb_id,
                "ingestion_job_id": job_id,
                "action_url": f"/knowledge-bases/{kb_id}?document_id={doc_id}",
                "dedupe_key": dedupe_key,
            }
        )

    async def publish_ingestion_timeout(
        self,
        *,
        kb_id: uuid.UUID,
        doc_id: uuid.UUID,
        job_id: uuid.UUID,
        doc_name: str,
        event_at: datetime | None = None,
    ) -> None:
        now = event_at or datetime.now(UTC)
        window = int(now.timestamp()) // TIMEOUT_WINDOW_SECONDS
        dedupe_key = f"ingestion_timeout:{job_id}:{window}"
        await self.repo.create_if_absent(
            {
                "user_id": self.user_id,
                "event_type": "ingestion_timeout",
                "level": "warning",
                "title": "文档处理超时",
                "message": f"《{doc_name}》处理耗时较长，仍在进行中",
                "resource_id": doc_id,
                "knowledge_base_id": kb_id,
                "ingestion_job_id": job_id,
                "action_url": f"/knowledge-bases/{kb_id}?document_id={doc_id}",
                "dedupe_key": dedupe_key,
            }
        )
