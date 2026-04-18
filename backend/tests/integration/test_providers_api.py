import pytest

pytestmark = pytest.mark.asyncio


async def test_create_and_list_provider(client, user_headers):
    payload = {
        "name": "My OpenAI",
        "provider_type": "openai",
        "api_key": "sk-test-1234567890abcdef",
        "base_url": None,
        "is_active": True,
    }
    resp = await client.post("/api/v1/providers", json=payload, headers=user_headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "My OpenAI"
    assert "api_key" not in created
    assert created["api_key_mask"].startswith("sk-t")
    assert created["api_key_mask"].endswith("cdef")

    resp = await client.get("/api/v1/providers", headers=user_headers)
    assert resp.status_code == 200
    listed = resp.json()
    assert len(listed) == 1
    # list 路径也必须返回真 mask,而不是占位符。
    assert listed[0]["api_key_mask"] == created["api_key_mask"]


async def test_update_api_key_refreshes_mask(client, user_headers):
    payload = {"name": "p", "provider_type": "openai", "api_key": "sk-oldkey12345678"}
    r = await client.post("/api/v1/providers", json=payload, headers=user_headers)
    pid = r.json()["id"]
    old_mask = r.json()["api_key_mask"]

    resp = await client.put(
        f"/api/v1/providers/{pid}",
        json={"api_key": "sk-newkey87654321"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    new_mask = resp.json()["api_key_mask"]
    assert new_mask != old_mask
    assert new_mask.startswith("sk-n")
    assert new_mask.endswith("4321")


async def test_delete_blocked_when_model_references(client, user_headers, session_maker):
    """provider 被 models 引用时 delete 必须 409,避免级联失活破坏评测血缘。"""
    import uuid

    from app.models.model import Model

    payload = {"name": "p", "provider_type": "openai", "api_key": "sk-abcdefgh12345678"}
    r = await client.post("/api/v1/providers", json=payload, headers=user_headers)
    pid = r.json()["id"]

    async with session_maker() as s:
        s.add(
            Model(
                id=uuid.uuid4(),
                provider_id=uuid.UUID(pid),
                model_id="gpt-4o",
                model_type="llm",
            )
        )
        await s.commit()

    resp = await client.delete(f"/api/v1/providers/{pid}", headers=user_headers)
    assert resp.status_code == 409
    assert "referenced" in resp.json()["detail"]

    # 仍然可读(未软删)。
    assert (await client.get(f"/api/v1/providers/{pid}", headers=user_headers)).status_code == 200


async def test_get_provider(client, user_headers):
    payload = {"name": "p", "provider_type": "openai", "api_key": "sk-abcdefgh12345678"}
    r = await client.post("/api/v1/providers", json=payload, headers=user_headers)
    pid = r.json()["id"]

    resp = await client.get(f"/api/v1/providers/{pid}", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


async def test_update_provider(client, user_headers):
    payload = {"name": "p", "provider_type": "openai", "api_key": "sk-abcdefgh12345678"}
    r = await client.post("/api/v1/providers", json=payload, headers=user_headers)
    pid = r.json()["id"]

    resp = await client.put(
        f"/api/v1/providers/{pid}",
        json={"name": "renamed", "is_active": False},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"
    assert resp.json()["is_active"] is False


async def test_delete_provider_soft_deletes(client, user_headers):
    payload = {"name": "p", "provider_type": "openai", "api_key": "sk-abcdefgh12345678"}
    r = await client.post("/api/v1/providers", json=payload, headers=user_headers)
    pid = r.json()["id"]

    resp = await client.delete(f"/api/v1/providers/{pid}", headers=user_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/providers/{pid}", headers=user_headers)
    assert resp.status_code == 404

    resp = await client.get("/api/v1/providers", headers=user_headers)
    assert resp.json() == []


async def test_multi_tenant_isolation(client):
    headers_a = {
        "X-User-Id": "github:user-a",
        "X-User-Email": "a@example.com",
        "X-User-Name": "A",
    }
    headers_b = {
        "X-User-Id": "github:user-b",
        "X-User-Email": "b@example.com",
        "X-User-Name": "B",
    }
    payload = {"name": "p", "provider_type": "openai", "api_key": "sk-abcdefgh12345678"}

    await client.post("/api/v1/providers", json=payload, headers=headers_a)
    resp_b = await client.get("/api/v1/providers", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json() == []


async def test_validation_rejects_unknown_provider_type(client, user_headers):
    payload = {"name": "p", "provider_type": "unknown-type", "api_key": "sk-x"}
    resp = await client.post("/api/v1/providers", json=payload, headers=user_headers)
    assert resp.status_code == 422


async def test_create_requires_auth(client):
    payload = {"name": "p", "provider_type": "openai", "api_key": "sk-x"}
    resp = await client.post("/api/v1/providers", json=payload)
    assert resp.status_code == 401
