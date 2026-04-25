import asyncio
import uuid

from app.core.celery_app import celery_app
from app.core.database import async_session_maker
from app.services.knowledge_base_service import KnowledgeBaseService

_worker_loop: asyncio.AbstractEventLoop | None = None


async def _run_ingestion(
    user_id: str,
    kb_id: str,
    doc_id: str,
    job_id: str,
) -> None:
    async with async_session_maker() as session:
        service = KnowledgeBaseService(session, uuid.UUID(user_id))
        await service.process_document_ingestion(
            kb_id=uuid.UUID(kb_id),
            doc_id=uuid.UUID(doc_id),
            job_id=uuid.UUID(job_id),
        )


def _run_async(coro) -> None:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)
    _worker_loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.ingestion.process_document_ingestion_task")
def process_document_ingestion_task(
    user_id: str,
    kb_id: str,
    doc_id: str,
    job_id: str,
) -> None:
    _run_async(_run_ingestion(user_id=user_id, kb_id=kb_id, doc_id=doc_id, job_id=job_id))
