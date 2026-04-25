import logging

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings
from app.core.database import engine

celery_app = Celery(
    "buildtest-ai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Keep startup reconnect behavior explicit for Celery 6 compatibility.
    broker_connection_retry_on_startup=True,
    # Allow retrying indefinitely when broker temporarily restarts.
    broker_connection_max_retries=None,
    # When broker connection drops, cancel running late-acked tasks so they can be redelivered.
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_always_eager=settings.celery_task_always_eager,
    include=["app.tasks.ingestion"],
)

celery_app.autodiscover_tasks(["app"])

logger = logging.getLogger(__name__)


@worker_process_init.connect
def _reset_db_pool_after_fork(**_: object) -> None:
    """
    Celery prefork workers inherit parent process state.
    Dispose SQLAlchemy pool in each child process to avoid reusing inherited
    asyncpg connections, which can cause "another operation is in progress".
    """
    engine.sync_engine.dispose()
    logger.info("Disposed SQLAlchemy pool in celery worker child process")
