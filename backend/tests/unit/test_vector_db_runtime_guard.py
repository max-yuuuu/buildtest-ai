import pytest

from app.schemas.vector_db import VectorDbTestResult


@pytest.mark.asyncio
async def test_create_active_vector_db_rejects_failed_probe(client, user_headers, monkeypatch):
    async def fake_probe(db_type: str, connection_string: str, api_key_plain: str | None):
        _ = (db_type, connection_string, api_key_plain)
        return VectorDbTestResult(ok=False, latency_ms=5, message="boom")

    monkeypatch.setattr("app.services.vector_db_service.vector_db_probe.probe", fake_probe)

    resp = await client.post(
        "/api/v1/vector-dbs",
        headers=user_headers,
        json={
            "name": "qdrant-main",
            "db_type": "qdrant",
            "connection_string": "http://localhost:6333",
            "api_key": None,
            "is_active": True,
        },
    )
    assert resp.status_code == 400
    assert "active vector db probe failed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_switching_active_vector_db_deactivates_previous(client, user_headers, monkeypatch):
    async def fake_probe(db_type: str, connection_string: str, api_key_plain: str | None):
        _ = (db_type, connection_string, api_key_plain)
        return VectorDbTestResult(ok=True, latency_ms=1, message="ok")

    monkeypatch.setattr("app.services.vector_db_service.vector_db_probe.probe", fake_probe)

    first = await client.post(
        "/api/v1/vector-dbs",
        headers=user_headers,
        json={
            "name": "pg",
            "db_type": "postgres_pgvector",
            "connection_string": "postgresql+asyncpg://u:p@localhost:5432/db",
            "api_key": None,
            "is_active": True,
        },
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = await client.post(
        "/api/v1/vector-dbs",
        headers=user_headers,
        json={
            "name": "qdrant",
            "db_type": "qdrant",
            "connection_string": "http://localhost:6333",
            "api_key": None,
            "is_active": True,
        },
    )
    assert second.status_code == 201

    listed = await client.get("/api/v1/vector-dbs", headers=user_headers)
    assert listed.status_code == 200
    by_id = {item["id"]: item for item in listed.json()}
    assert by_id[first_id]["is_active"] is False
    assert by_id[second.json()["id"]]["is_active"] is True


@pytest.mark.asyncio
async def test_active_probe_endpoint_uses_active_config(client, user_headers, monkeypatch):
    async def fake_probe(db_type: str, connection_string: str, api_key_plain: str | None):
        _ = connection_string
        return VectorDbTestResult(ok=True, latency_ms=3, message=f"ok:{db_type}:{api_key_plain or '-'}")

    monkeypatch.setattr("app.services.vector_db_service.vector_db_probe.probe", fake_probe)

    create_resp = await client.post(
        "/api/v1/vector-dbs",
        headers=user_headers,
        json={
            "name": "qdrant",
            "db_type": "qdrant",
            "connection_string": "http://localhost:6333",
            "api_key": "k123",
            "is_active": True,
        },
    )
    assert create_resp.status_code == 201

    probe_resp = await client.get("/api/v1/vector-dbs/active/probe", headers=user_headers)
    assert probe_resp.status_code == 200
    assert probe_resp.json()["ok"] is True
    assert probe_resp.json()["message"].startswith("ok:qdrant")
