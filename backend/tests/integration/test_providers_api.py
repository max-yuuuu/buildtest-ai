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
    assert len(resp.json()) == 1


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
