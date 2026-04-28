from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx


class OcrError(Exception):
    pass


@dataclass
class OcrResult:
    text: str
    lines: list[dict]
    words: list[dict]
    provider_impl: str


def _normalize_ocr_base_url(base_url: str | None) -> str:
    if not base_url:
        raise OcrError("OCR provider 缺少 base_url")
    return base_url.rstrip("/")


def _truncate_structured(items: list[dict], max_items: int = 200) -> list[dict]:
    return items[:max_items]


def _looks_like_dashscope_compatible(base_url: str) -> bool:
    lower = base_url.lower()
    return "dashscope" in lower and "/compatible-mode/v1" in lower


async def extract_text_from_image(
    *,
    provider_type: str,
    api_key: str,
    base_url: str | None,
    model_id: str,
    image_bytes: bytes,
    languages: list[str] | None = None,
) -> OcrResult:
    """
    OCR via provider-registered endpoint.
    Two modes:
    1) Self-hosted OCR HTTP: POST {base_url}/ocr
       Request: {"model": "...", "image_base64": "...", "languages": ["zh","en"]}
    2) DashScope OpenAI-compatible Qwen-VL-OCR:
       POST {base_url}/chat/completions with image_url(data URL) + prompt
    """
    endpoint_root = _normalize_ocr_base_url(base_url)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if _looks_like_dashscope_compatible(endpoint_root):
                encoded = base64.b64encode(image_bytes).decode("ascii")
                lang_hint = ",".join(languages or ["zh", "en"])
                prompt = (
                    "Please output only the text content from the image without any additional "
                    f"descriptions or formatting. Language hint: {lang_hint}."
                )
                payload = {
                    "model": model_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                }
                resp = await client.post(
                    f"{endpoint_root}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            else:
                encoded = base64.b64encode(image_bytes).decode("ascii")
                payload = {
                    "model": model_id,
                    "image_base64": encoded,
                    "languages": languages or ["zh", "en"],
                }
                resp = await client.post(f"{endpoint_root}/ocr", json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise OcrError(f"OCR 请求失败: {type(exc).__name__}: {exc}") from exc

    if resp.status_code >= 400:
        raise OcrError(f"OCR 接口返回错误 HTTP {resp.status_code}: {resp.text[:300]}")

    body = resp.json()
    if "choices" in body:
        try:
            text = str(body["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:
            raise OcrError("OCR 返回格式异常: 缺少 choices[0].message.content") from exc
        lines = []
        words = []
        impl = "dashscope.qwen_vl_ocr"
    else:
        text = str(body.get("text") or "").strip()
        lines = body.get("lines") if isinstance(body.get("lines"), list) else []
        words = body.get("words") if isinstance(body.get("words"), list) else []
        impl = f"{provider_type}.ocr_http"
    return OcrResult(
        text=text,
        lines=_truncate_structured(lines),
        words=_truncate_structured(words),
        provider_impl=impl,
    )
