import httpx

from app.services.embedding_client import embed_texts


class _StubResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> dict:
        return self._payload


class _StubAsyncClient:
    def __init__(self, responses: list[_StubResponse]) -> None:
        self._responses = list(responses)
        self.posts: list[tuple[str, dict]] = []

    async def __aenter__(self) -> "_StubAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict) -> _StubResponse:
        self.posts.append((url, json))
        if not self._responses:
            raise AssertionError("No more stubbed responses")
        return self._responses.pop(0)


async def test_ollama_embed_uses_api_embed_and_strips_v1(monkeypatch):
    stub = _StubAsyncClient(
        responses=[
            _StubResponse(
                200,
                payload={"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]},
            )
        ]
    )

    def _factory(*args, **kwargs):
        _ = args, kwargs
        return stub

    monkeypatch.setattr(httpx, "AsyncClient", _factory)

    vectors = await embed_texts(
        provider_type="ollama",
        api_key="",
        base_url="http://localhost:11434/v1",
        model_id="nomic-embed-text",
        texts=["a", "b"],
        batch_size=10,
    )

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert stub.posts[0][0] == "http://localhost:11434/api/embed"
    assert stub.posts[0][1]["input"] == ["a", "b"]


async def test_ollama_embed_falls_back_to_api_embeddings(monkeypatch):
    stub = _StubAsyncClient(
        responses=[
            _StubResponse(404, payload={}, text="not found"),
            _StubResponse(200, payload={"embedding": [1, 2]}),
            _StubResponse(200, payload={"embedding": [3, 4]}),
        ]
    )

    def _factory(*args, **kwargs):
        _ = args, kwargs
        return stub

    monkeypatch.setattr(httpx, "AsyncClient", _factory)

    vectors = await embed_texts(
        provider_type="ollama",
        api_key="",
        base_url="http://localhost:11434",
        model_id="nomic-embed-text",
        texts=["x", "y"],
    )

    assert vectors == [[1.0, 2.0], [3.0, 4.0]]
    assert stub.posts[0][0].endswith("/api/embed")
    assert stub.posts[1][0].endswith("/api/embeddings")
    assert stub.posts[2][0].endswith("/api/embeddings")
