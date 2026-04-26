import uuid

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.schemas.knowledge_base import (
    DocumentChunksResponse,
    DocumentRead,
    IngestionJobRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
    RebuildRequest,
    RetrieveRequest,
    RetrieveResponse,
)
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter()


def _svc(session: AsyncSession, user_id: uuid.UUID) -> KnowledgeBaseService:
    return KnowledgeBaseService(session, user_id)


@router.get("", response_model=list[KnowledgeBaseRead])
async def list_knowledge_bases(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeBaseRead]:
    return await _svc(session, user_id).list()


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeBaseRead:
    return await _svc(session, user_id).create(data)


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeBaseRead:
    return await _svc(session, user_id).get(kb_id)


@router.put("/{kb_id}", response_model=KnowledgeBaseRead)
async def update_knowledge_base(
    kb_id: uuid.UUID,
    data: KnowledgeBaseUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeBaseRead:
    return await _svc(session, user_id).update(kb_id, data)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _svc(session, user_id).delete(kb_id)


@router.get("/{kb_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    kb_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentRead]:
    return await _svc(session, user_id).list_documents(kb_id)


@router.post("/{kb_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> DocumentRead:
    return await _svc(session, user_id).upload_document(kb_id, file)


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _svc(session, user_id).delete_document(kb_id, doc_id)


@router.get("/{kb_id}/documents/{doc_id}/ingestion-job", response_model=IngestionJobRead)
async def get_latest_ingestion_job(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IngestionJobRead:
    return await _svc(session, user_id).get_latest_ingestion_job(kb_id, doc_id)


@router.get("/{kb_id}/documents/{doc_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    include_text: bool = Query(default=True),
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> DocumentChunksResponse:
    return await _svc(session, user_id).get_document_chunks(
        kb_id,
        doc_id,
        page=page,
        page_size=page_size,
        include_text=include_text,
    )


@router.post(
    "/{kb_id}/documents/{doc_id}/ingestion-job/retry",
    response_model=IngestionJobRead,
)
async def retry_latest_ingestion_job(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IngestionJobRead:
    return await _svc(session, user_id).retry_latest_ingestion_job(kb_id, doc_id)


@router.post("/{kb_id}/retrieve", response_model=RetrieveResponse)
async def retrieve(
    kb_id: uuid.UUID,
    body: RetrieveRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> RetrieveResponse:
    return await _svc(session, user_id).retrieve(kb_id, body)


@router.post("/{kb_id}/rebuild", status_code=status.HTTP_204_NO_CONTENT)
async def rebuild(
    kb_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    body: RebuildRequest | None = Body(default=None),
) -> None:
    await _svc(session, user_id).rebuild(kb_id, body or RebuildRequest())
