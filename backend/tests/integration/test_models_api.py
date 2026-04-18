import pytest

pytestmark = pytest.mark.asyncio


async def _create_provider(client, headers, name="p"):
    resp = await client.post(
        "/api/v1/providers",
        json={"name": name, "provider_type": "openai", "api_key": "sk-abcdefgh12345678"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_and_list_models(client, user_headers):
    pid = await _create_provider(client, user_headers)

    resp = await client.post(
        f"/api/v1/providers/{pid}/models",
        json={"model_id": "gpt-4o", "model_type": "llm", "context_window": 128000},
        headers=user_headers,
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["model_id"] == "gpt-4o"
    assert created["provider_id"] == pid

    resp = await client.get(f"/api/v1/providers/{pid}/models", headers=user_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_create_duplicate_model_rejected(client, user_headers):
    pid = await _create_provider(client, user_headers)
    payload = {"model_id": "gpt-4o", "model_type": "llm"}

    r1 = await client.post(f"/api/v1/providers/{pid}/models", json=payload, headers=user_headers)
    assert r1.status_code == 201

    r2 = await client.post(f"/api/v1/providers/{pid}/models", json=payload, headers=user_headers)
    assert r2.status_code == 409


async def test_embedding_requires_vector_dimension(client, user_headers):
    pid = await _create_provider(client, user_headers)
    resp = await client.post(
        f"/api/v1/providers/{pid}/models",
        json={"model_id": "text-embedding-3-small", "model_type": "embedding"},
        headers=user_headers,
    )
    assert resp.status_code == 422


async def test_embedding_with_dim_ok(client, user_headers):
    pid = await _create_provider(client, user_headers)
    resp = await client.post(
        f"/api/v1/providers/{pid}/models",
        json={
            "model_id": "text-embedding-3-small",
            "model_type": "embedding",
            "vector_dimension": 1536,
        },
        headers=user_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["vector_dimension"] == 1536


async def test_update_model(client, user_headers):
    pid = await _create_provider(client, user_headers)
    r = await client.post(
        f"/api/v1/providers/{pid}/models",
        json={"model_id": "gpt-4o", "model_type": "llm"},
        headers=user_headers,
    )
    mpk = r.json()["id"]

    resp = await client.put(
        f"/api/v1/providers/{pid}/models/{mpk}",
        json={"context_window": 256000},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["context_window"] == 256000


async def test_update_to_embedding_without_dim_rejected(client, user_headers):
    pid = await _create_provider(client, user_headers)
    r = await client.post(
        f"/api/v1/providers/{pid}/models",
        json={"model_id": "x", "model_type": "llm"},
        headers=user_headers,
    )
    mpk = r.json()["id"]

    resp = await client.put(
        f"/api/v1/providers/{pid}/models/{mpk}",
        json={"model_type": "embedding"},
        headers=user_headers,
    )
    assert resp.status_code == 422


async def test_delete_model(client, user_headers):
    pid = await _create_provider(client, user_headers)
    r = await client.post(
        f"/api/v1/providers/{pid}/models",
        json={"model_id": "gpt-4o", "model_type": "llm"},
        headers=user_headers,
    )
    mpk = r.json()["id"]

    resp = await client.delete(f"/api/v1/providers/{pid}/models/{mpk}", headers=user_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/providers/{pid}/models", headers=user_headers)
    assert resp.json() == []


async def test_multi_tenant_isolation_returns_404(client):
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
    pid_a = await _create_provider(client, headers_a)

    # B 用 A 的 provider_id,应 404(不泄漏存在性)
    resp = await client.get(f"/api/v1/providers/{pid_a}/models", headers=headers_b)
    assert resp.status_code == 404


async def test_list_available_calls_probe(client, user_headers, monkeypatch):
    pid = await _create_provider(client, user_headers)

    # 预注册一个,验证 is_registered 标记
    await client.post(
        f"/api/v1/providers/{pid}/models",
        json={"model_id": "gpt-4o", "model_type": "llm"},
        headers=user_headers,
    )

    from app.services import provider_probe

    async def fake_list_models(provider_type, api_key, base_url=None):
        assert provider_type == "openai"
        assert api_key == "sk-abcdefgh12345678"  # 解密后应为明文
        return ["gpt-4o", "gpt-4o-mini"]

    monkeypatch.setattr(provider_probe, "list_models", fake_list_models)

    resp = await client.get(f"/api/v1/providers/{pid}/models/available", headers=user_headers)
    assert resp.status_code == 200
    items = {item["model_id"]: item for item in resp.json()}
    assert items["gpt-4o"]["is_registered"] is True
    assert items["gpt-4o-mini"]["is_registered"] is False


async def test_list_available_probe_error_502(client, user_headers, monkeypatch):
    pid = await _create_provider(client, user_headers)

    from app.services import provider_probe

    async def boom(provider_type, api_key, base_url=None):
        raise provider_probe.ProbeError("auth", "bad key", 401)

    monkeypatch.setattr(provider_probe, "list_models", boom)

    resp = await client.get(f"/api/v1/providers/{pid}/models/available", headers=user_headers)
    assert resp.status_code == 502
