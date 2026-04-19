"""调用 Provider 的 Embedding API（Phase 1：OpenAI 兼容端点）。"""

from __future__ import annotations


class EmbeddingError(Exception):
    pass


async def embed_texts(
    *,
    provider_type: str,
    api_key: str,
    base_url: str | None,
    model_id: str,
    texts: list[str],
) -> list[list[float]]:
    if provider_type not in ("openai", "azure"):
        raise EmbeddingError(f"embedding 尚未支持 provider_type={provider_type}")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
    out: list[list[float]] = []
    batch = 64
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        resp = await client.embeddings.create(model=model_id, input=chunk)
        for item in resp.data:
            out.append(list(item.embedding))
    if len(out) != len(texts):
        raise EmbeddingError("embedding 返回条数与输入不一致")
    return out
