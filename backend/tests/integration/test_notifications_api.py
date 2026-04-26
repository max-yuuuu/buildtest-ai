import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.notification import Notification
from app.services.notification_service import NotificationService

pytestmark = pytest.mark.asyncio


async def _seed_notification(session, user_id: uuid.UUID, *, is_read: bool = False) -> Notification:
    row = Notification(
        user_id=user_id,
        event_type="ingestion_completed",
        level="success",
        title="文档处理完成",
        message="《a.txt》处理完成，可开始检索",
        is_read=is_read,
        resource_type="knowledge_base_document",
        resource_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        ingestion_job_id=uuid.uuid4(),
        action_url="/knowledge-bases/x/documents/y/chunks",
        dedupe_key=f"seed:{uuid.uuid4()}",
    )
    session.add(row)
    await session.commit()
    return row


async def test_notifications_list_unread_and_mark_read(client, user_headers, session):
    from app.api.v1.deps import get_current_user_id
    from app.main import app

    user_id = uuid.uuid4()

    async def override_user_id():
        return user_id

    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        first = await _seed_notification(session, user_id, is_read=False)
        await _seed_notification(session, user_id, is_read=True)

        list_res = await client.get(
            "/api/v1/notifications", headers=user_headers, params={"page": 1, "page_size": 20}
        )
        assert list_res.status_code == 200
        payload = list_res.json()
        assert payload["total"] == 2
        assert len(payload["items"]) == 2

        count_res = await client.get("/api/v1/notifications/unread-count", headers=user_headers)
        assert count_res.status_code == 200
        assert count_res.json()["unread_count"] == 1

        mark_res = await client.post(
            "/api/v1/notifications/mark-read",
            json={"notification_ids": [first.id.hex, first.id.hex]},
            headers=user_headers,
        )
        assert mark_res.status_code == 200
        assert mark_res.json()["updated"] == 1

        count_again = await client.get("/api/v1/notifications/unread-count", headers=user_headers)
        assert count_again.status_code == 200
        assert count_again.json()["unread_count"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


async def test_notifications_tenant_isolation(client, user_headers, session):
    from app.api.v1.deps import get_current_user_id
    from app.main import app

    current_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    async def override_user_id():
        return current_user_id

    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        await _seed_notification(session, other_user_id, is_read=False)
        response = await client.get("/api/v1/notifications", headers=user_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


async def test_timeout_notification_dedupes_in_30m_window(session):
    user_id = uuid.uuid4()
    service = NotificationService(session, user_id)
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    await service.publish_ingestion_timeout(
        kb_id=uuid.uuid4(),
        doc_id=uuid.uuid4(),
        job_id=job_id,
        doc_name="large.pdf",
        event_at=now,
    )
    await service.publish_ingestion_timeout(
        kb_id=uuid.uuid4(),
        doc_id=uuid.uuid4(),
        job_id=job_id,
        doc_name="large.pdf",
        event_at=now,
    )
    await session.commit()

    rows = (
        await session.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.event_type == "ingestion_timeout",
                Notification.ingestion_job_id == job_id,
            )
        )
    ).scalars()
    assert len(list(rows)) == 1
