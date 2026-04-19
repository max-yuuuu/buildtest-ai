import pytest

pytestmark = pytest.mark.asyncio


async def test_create_list_get_delete_vector_db(client, user_headers):
    payload = {
        "name": "本地 Qdrant",
        "db_type": "qdrant",
        "connection_string": "http://127.0.0.1:6333",
        "api_key": None,
        "is_active": True,
    }
    resp = await client.post("/api/v1/vector-dbs", json=payload, headers=user_headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "本地 Qdrant"
    assert created["db_type"] == "qdrant"
    assert "connection_string" not in created
    assert "http" in created["connection_string_mask"] or "***" in created["connection_string_mask"]

    resp = await client.get("/api/v1/vector-dbs", headers=user_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    cid = created["id"]
    resp = await client.get(f"/api/v1/vector-dbs/{cid}", headers=user_headers)
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v1/vector-dbs/{cid}", headers=user_headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/vector-dbs", headers=user_headers)
    assert resp.json() == []


async def test_test_vector_db_returns_result_shape(client, user_headers):
    payload = {
        "name": "pg",
        "db_type": "postgres_pgvector",
        "connection_string": "postgresql://nouser:nopass@127.0.0.1:59999/nodb",
        "is_active": True,
    }
    r = await client.post("/api/v1/vector-dbs", json=payload, headers=user_headers)
    assert r.status_code == 201
    cid = r.json()["id"]

    resp = await client.post(f"/api/v1/vector-dbs/{cid}/test", headers=user_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "ok" in body
    assert "latency_ms" in body
    assert "message" in body
    assert body["ok"] is False
