"""调用 Provider 的 Embedding API（Phase 1：OpenAI 兼容端点）。"""

from __future__ import annotations

import re

DEFAULT_BATCH_SIZE = 64


class EmbeddingError(Exception):
    pass


def _extract_batch_limit(message: str) -> int | None:
    matched = re.search(r"should not be larger than\s+(\d+)", message, flags=re.IGNORECASE)
    if matched:
        return int(matched.group(1))
    return None


async def embed_texts(
    *,
    provider_type: str,
    api_key: str,
    base_url: str | None,
    model_id: str,
    texts: list[str],
    batch_size: int | None = None,
) -> list[list[float]]:
    if provider_type not in ("openai", "azure"):
        raise EmbeddingError(f"embedding 尚未支持 provider_type={provider_type}")

    from openai import APIConnectionError, APIStatusError, AsyncOpenAI

    if not api_key:
        raise EmbeddingError("provider 未配置 api_key")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url or None, timeout=60.0)
    effective_url = base_url or "https://api.openai.com/v1"
    out: list[list[float]] = []
    batch = batch_size if batch_size and batch_size > 0 else DEFAULT_BATCH_SIZE
    idx = 0
    try:
        while idx < len(texts):
            chunk = texts[idx : idx + batch]
            try:
                resp = await client.embeddings.create(model=model_id, input=chunk)
            except APIStatusError as e:
                body = getattr(e, "message", None) or str(e)
                limit = _extract_batch_limit(body)
                is_batch_error = (
                    e.status_code == 400
                    and limit is not None
                    and "batch size" in body.lower()
                    and batch > limit > 0
                )
                if is_batch_error:
                    batch = limit
                    continue
                raise
            for item in resp.data:
                out.append(list(item.embedding))
            idx += len(chunk)
    except APIConnectionError as e:
        cause = getattr(e, "__cause__", None) or e
        raise EmbeddingError(
            f"连接 embedding 接口失败: {type(cause).__name__}: {cause} "
            f"(base_url={effective_url}, model={model_id})"
        ) from e
    except APIStatusError as e:
        body = getattr(e, "message", None) or str(e)
        limit = _extract_batch_limit(body)
        suggestion = f"；建议将 embedding_batch_size 设置为 {limit}" if limit is not None else ""
        raise EmbeddingError(
            f"embedding 接口返回错误 HTTP {e.status_code}: {body}{suggestion} "
            f"(base_url={effective_url}, model={model_id})"
        ) from e
    if len(out) != len(texts):
        raise EmbeddingError("embedding 返回条数与输入不一致")
    return out
