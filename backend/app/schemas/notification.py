import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    level: str
    title: str
    message: str
    is_read: bool
    resource_type: str
    resource_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    ingestion_job_id: uuid.UUID
    action_url: str
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[NotificationRead]


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadRequest(BaseModel):
    notification_ids: list[uuid.UUID] = Field(default_factory=list)


class MarkReadResponse(BaseModel):
    updated: int
