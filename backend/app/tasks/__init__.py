"""Celery tasks package."""

# Ensure ingestion task is imported so Celery worker registers it.
from app.tasks.ingestion import process_document_ingestion_task

__all__ = ["process_document_ingestion_task"]
