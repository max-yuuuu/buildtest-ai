import pytest

pytestmark = pytest.mark.asyncio


async def test_me_upsert_user(client, user_headers):
    resp = await client.get("/api/v1/users/me", headers=user_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_id"] == user_headers["X-User-Id"]
    assert body["email"] == "test@example.com"
    assert body["name"] == "Test User"


async def test_me_requires_x_user_id(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_me_is_idempotent(client, user_headers):
    r1 = await client.get("/api/v1/users/me", headers=user_headers)
    r2 = await client.get("/api/v1/users/me", headers=user_headers)
    assert r1.json()["id"] == r2.json()["id"]
