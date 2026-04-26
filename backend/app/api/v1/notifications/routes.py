import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_id, get_session
from app.schemas.notification import (
    MarkReadRequest,
    MarkReadResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter()


def _raise_if_notifications_table_missing(exc: ProgrammingError) -> None:
    message = str(exc).lower()
    if 'relation "notifications" does not exist' in message:
        raise HTTPException(
            status_code=503,
            detail="通知中心尚未完成数据库迁移，请先执行 `alembic upgrade head` 并重启后端服务",
        ) from exc
    raise exc


def _svc(session: AsyncSession, user_id: uuid.UUID) -> NotificationService:
    return NotificationService(session, user_id)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    unread_only: bool = Query(default=False),
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> NotificationListResponse:
    try:
        return await _svc(session, user_id).list_notifications(
            page=page, page_size=page_size, unread_only=unread_only
        )
    except ProgrammingError as exc:
        _raise_if_notifications_table_missing(exc)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> UnreadCountResponse:
    try:
        count = await _svc(session, user_id).unread_count()
        return UnreadCountResponse(unread_count=count)
    except ProgrammingError as exc:
        _raise_if_notifications_table_missing(exc)


@router.post("/mark-read", response_model=MarkReadResponse)
async def mark_read(
    body: MarkReadRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MarkReadResponse:
    try:
        updated = await _svc(session, user_id).mark_read(body.notification_ids)
        await session.commit()
        return MarkReadResponse(updated=updated)
    except ProgrammingError as exc:
        _raise_if_notifications_table_missing(exc)
