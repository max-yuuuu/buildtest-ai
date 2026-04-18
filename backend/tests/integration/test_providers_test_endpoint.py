import pytest

pytestmark = pytest.mark.asyncio


async def _create_provider(client, headers):
    resp = await client.post(
        "/api/v1/providers",
        json={"name": "p", "provider_type": "openai", "api_key": "sk-abcdefgh12345678"},
        headers=headers,
    )
    return resp.json()["id"]


async def test_test_connection_ok(client, user_headers, monkeypatch):
    pid = await _create_provider(client, user_headers)

    from app.services import provider_probe

    async def fake_list_models(provider_type, api_key, base_url=None):
        assert provider_type == "openai"
        # 关键:这里应拿到的是明文 key,说明 EncryptedString 正确解密
        assert api_key == "sk-abcdefgh12345678"
        return ["gpt-4o", "gpt-4o-mini"]

    monkeypatch.setattr(provider_probe, "list_models", fake_list_models)

    resp = await client.post(f"/api/v1/providers/{pid}/test", headers=user_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["message"] == "ok"
    assert "gpt-4o" in body["models"]
    assert body["latency_ms"] >= 0


async def test_test_connection_auth_failure_returns_200_ok_false(client, user_headers, monkeypatch):
    pid = await _create_provider(client, user_headers)

    from app.services import provider_probe

    async def bad(provider_type, api_key, base_url=None):
        raise provider_probe.ProbeError("auth", "invalid api key", 401)

    monkeypatch.setattr(provider_probe, "list_models", bad)

    resp = await client.post(f"/api/v1/providers/{pid}/test", headers=user_headers)
    # 连通性失败不是 HTTP 错误,只是结果
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "auth" in body["message"].lower()
    assert body["models"] == []


async def test_test_connection_timeout(client, user_headers, monkeypatch):
    pid = await _create_provider(client, user_headers)

    from app.services import provider_probe

    async def slow(provider_type, api_key, base_url=None):
        raise provider_probe.ProbeError("timeout", "upstream timed out after 10s")

    monkeypatch.setattr(provider_probe, "list_models", slow)

    resp = await client.post(f"/api/v1/providers/{pid}/test", headers=user_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "timeout" in body["message"].lower()


async def test_test_connection_provider_not_found(client, user_headers):
    import uuid

    fake = uuid.uuid4()
    resp = await client.post(f"/api/v1/providers/{fake}/test", headers=user_headers)
    assert resp.status_code == 404


async def test_test_connection_multi_tenant_isolation(client, monkeypatch):
    from app.services import provider_probe

    async def ok(provider_type, api_key, base_url=None):
        return []

    monkeypatch.setattr(provider_probe, "list_models", ok)

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

    resp = await client.post(f"/api/v1/providers/{pid_a}/test", headers=headers_b)
    assert resp.status_code == 404
