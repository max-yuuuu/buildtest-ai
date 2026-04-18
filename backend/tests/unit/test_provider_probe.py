import httpx
import pytest

from app.services import provider_probe
from app.services.provider_probe import ProbeError

pytestmark = pytest.mark.asyncio


def _fake_response(status: int, body: dict | None = None, text: str = "") -> httpx.Response:
    import json

    content = json.dumps(body).encode() if body is not None else text.encode()
    return httpx.Response(
        status_code=status, content=content, request=httpx.Request("GET", "http://x")
    )


async def test_openai_success(monkeypatch):
    captured: dict = {}

    async def fake_get(url: str, headers: dict[str, str]) -> httpx.Response:
        captured["url"] = url
        captured["headers"] = headers
        return _fake_response(200, {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]})

    monkeypatch.setattr(provider_probe, "_get", fake_get)
    models = await provider_probe.list_models("openai", "sk-test-1234567890abcdef")
    assert models == ["gpt-4o", "gpt-4o-mini"]
    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-1234567890abcdef"


async def test_openai_custom_base_url_strips_trailing_slash(monkeypatch):
    captured: dict = {}

    async def fake_get(url: str, headers: dict[str, str]) -> httpx.Response:
        captured["url"] = url
        return _fake_response(200, {"data": []})

    monkeypatch.setattr(provider_probe, "_get", fake_get)
    await provider_probe.list_models("openai", "sk-x", base_url="https://proxy.example/v1/")
    assert captured["url"] == "https://proxy.example/v1/models"


async def test_anthropic_success(monkeypatch):
    captured: dict = {}

    async def fake_get(url: str, headers: dict[str, str]) -> httpx.Response:
        captured["url"] = url
        captured["headers"] = headers
        return _fake_response(200, {"data": [{"id": "claude-3-5-sonnet-20241022"}]})

    monkeypatch.setattr(provider_probe, "_get", fake_get)
    models = await provider_probe.list_models("anthropic", "anthro-key-abc")
    assert models == ["claude-3-5-sonnet-20241022"]
    assert captured["url"] == "https://api.anthropic.com/v1/models"
    assert captured["headers"]["x-api-key"] == "anthro-key-abc"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"


async def test_azure_requires_base_url():
    with pytest.raises(ProbeError) as exc:
        await provider_probe.list_models("azure", "key")
    assert exc.value.kind == "config"


async def test_azure_success(monkeypatch):
    captured: dict = {}

    async def fake_get(url: str, headers: dict[str, str]) -> httpx.Response:
        captured["url"] = url
        captured["headers"] = headers
        return _fake_response(200, {"data": [{"id": "dep-1", "model": "gpt-4"}]})

    monkeypatch.setattr(provider_probe, "_get", fake_get)
    models = await provider_probe.list_models(
        "azure", "azkey", base_url="https://foo.openai.azure.com"
    )
    assert models == ["dep-1"]
    assert "api-version=2024-02-01" in captured["url"]
    assert captured["headers"]["api-key"] == "azkey"


async def test_zhipu_requires_base_url():
    with pytest.raises(ProbeError) as exc:
        await provider_probe.list_models("zhipu", "key")
    assert exc.value.kind == "config"


async def test_unsupported_provider_type():
    with pytest.raises(ProbeError) as exc:
        await provider_probe.list_models("unknown", "key")
    assert exc.value.kind == "config"


async def test_auth_failure_classified(monkeypatch):
    async def fake_get(url: str, headers: dict[str, str]) -> httpx.Response:
        return _fake_response(401, text="unauthorized")

    monkeypatch.setattr(provider_probe, "_get", fake_get)
    with pytest.raises(ProbeError) as exc:
        await provider_probe.list_models("openai", "bad-key")
    assert exc.value.kind == "auth"
    assert exc.value.status_code == 401


async def test_non_auth_4xx_classified_as_unknown(monkeypatch):
    async def fake_get(url: str, headers: dict[str, str]) -> httpx.Response:
        return _fake_response(500, text="upstream error")

    monkeypatch.setattr(provider_probe, "_get", fake_get)
    with pytest.raises(ProbeError) as exc:
        await provider_probe.list_models("openai", "key")
    assert exc.value.kind == "unknown"
    assert exc.value.status_code == 500


async def test_timeout_classified(monkeypatch):
    async def boom(url, headers, timeout=None):
        raise httpx.ReadTimeout("slow", request=httpx.Request("GET", url))

    # patch the lower-level httpx.AsyncClient.get through _get's internals
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, headers=None):
            raise httpx.ReadTimeout("slow", request=httpx.Request("GET", url))

    monkeypatch.setattr(provider_probe.httpx, "AsyncClient", FakeClient)
    with pytest.raises(ProbeError) as exc:
        await provider_probe.list_models("openai", "key")
    assert exc.value.kind == "timeout"


async def test_connect_error_classified(monkeypatch):
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, headers=None):
            raise httpx.ConnectError("no route", request=httpx.Request("GET", url))

    monkeypatch.setattr(provider_probe.httpx, "AsyncClient", FakeClient)
    with pytest.raises(ProbeError) as exc:
        await provider_probe.list_models("openai", "key")
    assert exc.value.kind == "network"
