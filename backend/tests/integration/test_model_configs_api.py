import pytest

pytestmark = pytest.mark.asyncio


async def _create_provider(client, headers, name="mcfg"):
    resp = await client.post(
        "/api/v1/providers",
        json={"name": name, "provider_type": "openai", "api_key": "sk-abcdefgh12345678"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_model(client, headers, provider_id, model_id, model_type, vector_dimension=None):
    payload = {"model_id": model_id, "model_type": model_type}
    if vector_dimension is not None:
        payload["vector_dimension"] = vector_dimension
    resp = await client.post(f"/api/v1/providers/{provider_id}/models", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_vector_db(client, headers):
    resp = await client.post(
        "/api/v1/vector-dbs",
        json={
            "name": "mcfg-pg",
            "db_type": "postgres_pgvector",
            "connection_string": "postgresql://x:y@127.0.0.1:9/db",
            "is_active": False,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_kb(client, headers, vector_db_id, embedding_model_id):
    resp = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "mcfg-kb",
            "vector_db_config_id": vector_db_id,
            "embedding_model_id": embedding_model_id,
            "chunk_size": 200,
            "chunk_overlap": 20,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_kb_model_configs_put_and_get(client, user_headers):
    pid = await _create_provider(client, user_headers)
    embedding_id = await _create_model(
        client, user_headers, pid, "text-embedding-3-small", "embedding", vector_dimension=1536
    )
    llm_id = await _create_model(client, user_headers, pid, "gpt-4o", "llm")
    vid = await _create_vector_db(client, user_headers)
    kb_id = await _create_kb(client, user_headers, vid, embedding_id)

    resp = await client.put(
        f"/api/v1/knowledge-bases/{kb_id}/model-configs",
        json=[
            {"purpose": "embedding", "model_id": embedding_id},
            {"purpose": "llm", "model_id": llm_id},
        ],
        headers=user_headers,
    )
    assert resp.status_code == 200, resp.text
    got = {item["purpose"]: item["model_id"] for item in resp.json()}
    assert got["embedding"] == embedding_id
    assert got["llm"] == llm_id

    listed = await client.get(f"/api/v1/knowledge-bases/{kb_id}/model-configs", headers=user_headers)
    assert listed.status_code == 200
    got2 = {item["purpose"]: item["model_id"] for item in listed.json()}
    assert got2 == got


async def test_kb_model_configs_fallback_to_legacy_embedding(client, user_headers):
    pid = await _create_provider(client, user_headers)
    embedding_id = await _create_model(
        client, user_headers, pid, "text-embedding-3-small", "embedding", vector_dimension=1536
    )
    vid = await _create_vector_db(client, user_headers)
    kb_id = await _create_kb(client, user_headers, vid, embedding_id)

    listed = await client.get(f"/api/v1/knowledge-bases/{kb_id}/model-configs", headers=user_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["purpose"] == "embedding"
    assert listed.json()[0]["model_id"] == embedding_id


async def test_agent_model_configs_upsert_requires_llm(client, user_headers):
    pid = await _create_provider(client, user_headers)
    llm_id = await _create_model(client, user_headers, pid, "gpt-4o", "llm")
    vlm_id = await _create_model(client, user_headers, pid, "qwen-vl-max", "vlm")

    ok = await client.put(
        "/api/v1/agent-configs/smart_agent",
        json={"model_id": llm_id},
        headers=user_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["agent_id"] == "smart_agent"
    assert ok.json()["model_id"] == llm_id

    bad = await client.put(
        "/api/v1/agent-configs/quick_chat",
        json={"model_id": vlm_id},
        headers=user_headers,
    )
    assert bad.status_code == 422

    listed = await client.get("/api/v1/agent-configs", headers=user_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
