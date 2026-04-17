from celery import Celery

from app.core.config import settings

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
    task_always_eager=settings.celery_task_always_eager,
)

celery_app.autodiscover_tasks(["app.tasks"])
