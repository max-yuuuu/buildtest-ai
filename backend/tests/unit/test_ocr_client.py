import pytest

from app.services.ocr_client import OcrError, extract_text_from_image


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _ = (exc_type, exc, tb)
        return False

    async def post(self, url: str, json: dict, headers: dict):  # noqa: A002
        assert url.endswith("/ocr")
        assert "image_base64" in json
        assert "languages" in json
        assert headers["Content-Type"] == "application/json"
        return self._response


@pytest.mark.asyncio
async def test_extract_text_from_image_success(monkeypatch):
    import app.services.ocr_client as mod

    monkeypatch.setattr(
        mod.httpx,
        "AsyncClient",
        lambda timeout=60.0: _FakeClient(
            _FakeResponse(
                200,
                {
                    "text": "hello ocr",
                    "lines": [{"text": "hello", "confidence": 0.99}],
                    "words": [{"text": "hello", "bbox": [0, 0, 1, 1], "confidence": 0.99}],
                },
            )
        ),
    )
    result = await extract_text_from_image(
        provider_type="openai",
        api_key="k",
        base_url="http://localhost:18080",
        model_id="paddleocr-v5",
        image_bytes=b"img",
        languages=["zh", "en"],
    )
    assert result.text == "hello ocr"
    assert result.lines[0]["text"] == "hello"
    assert result.provider_impl == "openai.ocr_http"


@pytest.mark.asyncio
async def test_extract_text_from_image_keeps_multilingual_languages(monkeypatch):
    import app.services.ocr_client as mod

    captured = {}

    class _CaptureClient(_FakeClient):
        async def post(self, url: str, json: dict, headers: dict):  # noqa: A002
            captured["languages"] = json.get("languages")
            return self._response

    monkeypatch.setattr(
        mod.httpx,
        "AsyncClient",
        lambda timeout=60.0: _CaptureClient(_FakeResponse(200, {"text": "中英 mixed"})),
    )
    result = await extract_text_from_image(
        provider_type="openai",
        api_key="k",
        base_url="http://localhost:18080",
        model_id="paddleocr-v5",
        image_bytes=b"img",
        languages=["zh", "en"],
    )
    assert captured["languages"] == ["zh", "en"]
    assert "mixed" in result.text


@pytest.mark.asyncio
async def test_extract_text_from_image_http_error(monkeypatch):
    import app.services.ocr_client as mod

    monkeypatch.setattr(
        mod.httpx,
        "AsyncClient",
        lambda timeout=60.0: _FakeClient(_FakeResponse(500, {}, text="boom")),
    )
    with pytest.raises(OcrError, match="HTTP 500"):
        await extract_text_from_image(
            provider_type="openai",
            api_key="",
            base_url="http://localhost:18080",
            model_id="paddleocr-v5",
            image_bytes=b"img",
            languages=["zh", "en"],
        )


@pytest.mark.asyncio
async def test_extract_text_from_image_dashscope_uses_chat_completions(monkeypatch):
    import app.services.ocr_client as mod

    class _CaptureClient(_FakeClient):
        async def post(self, url: str, json: dict, headers: dict):  # noqa: A002
            assert url.endswith("/chat/completions")
            assert json["model"] == "qwen-vl-ocr-2025-11-20"
            content = json["messages"][0]["content"]
            assert any(part.get("type") == "image_url" for part in content)
            assert any(part.get("type") == "text" for part in content)
            return self._response

    monkeypatch.setattr(
        mod.httpx,
        "AsyncClient",
        lambda timeout=60.0: _CaptureClient(
            _FakeResponse(
                200,
                {"choices": [{"message": {"content": "OCR RESULT"}}]},
            )
        ),
    )
    result = await extract_text_from_image(
        provider_type="qwen",
        api_key="k",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen-vl-ocr-2025-11-20",
        image_bytes=b"img",
        languages=["zh", "en"],
    )
    assert result.text == "OCR RESULT"
    assert result.provider_impl == "dashscope.qwen_vl_ocr"
