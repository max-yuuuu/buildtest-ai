from __future__ import annotations

from types import SimpleNamespace

import openai

from app.services.embedding_client import embed_texts


class _StubEmbeddings:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    async def create(self, *, model: str, input: list[str]):
        self.calls.append((model, input))
        # Mimic OpenAI embeddings response shape.
        data = [
            SimpleNamespace(embedding=[0.1, 0.2, 0.3 + i])  # type: ignore[arg-type]
            for i in range(len(input))
        ]
        return SimpleNamespace(data=data)


class _StubAsyncOpenAI:
    def __init__(self, *, api_key: str, base_url: str, timeout: float, http_client) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.http_client = http_client
        self.embeddings = _StubEmbeddings()

    async def __aenter__(self) -> "_StubAsyncOpenAI":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


async def test_qwen_embed_uses_openai_compatible_flow(monkeypatch):
    created: dict[str, object] = {}

    class _CapturingAsyncOpenAI(_StubAsyncOpenAI):
        def __init__(self, *, api_key: str, base_url: str, timeout: float, http_client) -> None:
            super().__init__(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                http_client=http_client,
            )
            created["base_url"] = base_url
            created["api_key"] = api_key
            created["embeddings_api"] = self.embeddings

    monkeypatch.setattr(openai, "AsyncOpenAI", _CapturingAsyncOpenAI)

    vectors = await embed_texts(
        provider_type="qwen",
        api_key="qwen-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
        model_id="text-embedding-v3",
        texts=["a", "b"],
        batch_size=10,
    )

    assert created["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert created["api_key"] == "qwen-api-key"
    assert vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 1.3]]
    embeddings_api: _StubEmbeddings = created["embeddings_api"]  # type: ignore[assignment]
    assert embeddings_api.calls == [("text-embedding-v3", ["a", "b"])]


async def test_provider_type_is_normalized(monkeypatch):
    created: dict[str, object] = {}

    class _CapturingAsyncOpenAI(_StubAsyncOpenAI):
        def __init__(self, *, api_key: str, base_url: str, timeout: float, http_client) -> None:
            super().__init__(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                http_client=http_client,
            )
            created["base_url"] = base_url
            created["api_key"] = api_key

    monkeypatch.setattr(openai, "AsyncOpenAI", _CapturingAsyncOpenAI)

    await embed_texts(
        provider_type="  QwEn  ",
        api_key="qwen-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
        model_id="text-embedding-v3",
        texts=["a"],
        batch_size=10,
    )

    assert created["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert created["api_key"] == "qwen-api-key"

