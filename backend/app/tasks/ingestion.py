import asyncio
import threading
import uuid

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_maker
from app.services.knowledge_base_service import KnowledgeBaseService

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
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        error: Exception | None = None

        def _runner() -> None:
            nonlocal error
            try:
                asyncio.run(coro)
            except Exception as exc:  # pragma: no cover - re-raised below
                error = exc

        thread = threading.Thread(target=_runner)
        thread.start()
        thread.join()
        if error is not None:
            raise error
        return

    asyncio.run(coro)


@celery_app.task(name="app.tasks.ingestion.process_document_ingestion_task")
def process_document_ingestion_task(
    user_id: str,
    kb_id: str,
    doc_id: str,
    job_id: str,
) -> None:
    _run_async(_run_ingestion(user_id=user_id, kb_id=kb_id, doc_id=doc_id, job_id=job_id))


@celery_app.task(name="app.tasks.ingestion.process_batch_ingestion_task")
def process_batch_ingestion_task(
    user_id: str,
    kb_id: str,
    doc_ids: list[str],
    job_ids: list[str],
) -> None:
    async def _run_batch() -> None:
        sem = asyncio.Semaphore(settings.kb_batch_max_concurrency)

        async def _with_semaphore(doc_id: str, job_id: str) -> None:
            async with sem:
                await _run_ingestion(
                    user_id=user_id, kb_id=kb_id, doc_id=doc_id, job_id=job_id
                )

        await asyncio.gather(
            *[_with_semaphore(did, jid) for did, jid in zip(doc_ids, job_ids, strict=True)]
        )

    _run_async(_run_batch())
