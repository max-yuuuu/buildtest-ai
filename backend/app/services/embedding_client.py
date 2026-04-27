"""调用 Provider 的 Embedding API（Phase 1：OpenAI 兼容端点）。"""

from __future__ import annotations

import re

DEFAULT_BATCH_SIZE = 64
_OPENAI_COMPAT_ENDPOINT_SUFFIXES = (
    "/embeddings",
    "/chat/completions",
    "/completions",
    "/responses",
    "/models",
)


class EmbeddingError(Exception):
    pass


def _strip_slash(url: str) -> str:
    return url.rstrip("/")


def _normalize_ollama_base_url(base_url: str | None) -> str:
    if not base_url:
        raise EmbeddingError("ollama provider 需要配置 base_url")
    u = _strip_slash(base_url.strip())
    if u.lower().endswith("/v1"):
        u = u[: -len("/v1")]
    return _strip_slash(u)


def _extract_batch_limit(message: str) -> int | None:
    matched = re.search(r"should not be larger than\s+(\d+)", message, flags=re.IGNORECASE)
    if matched:
        return int(matched.group(1))
    return None


def _normalize_openai_compatible_base_url(base_url: str | None) -> str:
    """Normalize user-provided endpoint URL to an OpenAI-compatible API root."""
    if not base_url:
        return "https://api.openai.com/v1"
    normalized = base_url.strip().rstrip("/")
    lower = normalized.lower()
    for suffix in _OPENAI_COMPAT_ENDPOINT_SUFFIXES:
        if lower.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized.rstrip("/")


async def embed_texts(
    *,
    provider_type: str,
    api_key: str,
    base_url: str | None,
    model_id: str,
    texts: list[str],
    batch_size: int | None = None,
) -> list[list[float]]:
    if provider_type not in ("openai", "azure", "ollama"):
        raise EmbeddingError(f"embedding 尚未支持 provider_type={provider_type}")

    if provider_type == "ollama":
        import httpx

        effective_url = _normalize_ollama_base_url(base_url)
        out: list[list[float]] = []
        batch = batch_size if batch_size and batch_size > 0 else DEFAULT_BATCH_SIZE
        idx = 0
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                while idx < len(texts):
                    chunk = texts[idx : idx + batch]
                    # Prefer the batch endpoint; fall back to legacy single-prompt endpoint.
                    resp = await client.post(
                        f"{effective_url}/api/embed",
                        json={"model": model_id, "input": chunk},
                    )
                    if resp.status_code == 404:
                        embeddings: list[list[float]] = []
                        for t in chunk:
                            r = await client.post(
                                f"{effective_url}/api/embeddings",
                                json={"model": model_id, "prompt": t},
                            )
                            if r.status_code >= 400:
                                raise EmbeddingError(
                                    f"embedding 接口返回错误 HTTP {r.status_code}: {r.text[:200]} "
                                    f"(base_url={effective_url}, model={model_id})"
                                )
                            data = r.json()
                            vec = data.get("embedding")
                            if not isinstance(vec, list) or not vec:
                                raise EmbeddingError("embedding 返回格式异常: 缺少 embedding 字段")
                            embeddings.append([float(x) for x in vec])
                    elif resp.status_code >= 400:
                        raise EmbeddingError(
                            f"embedding 接口返回错误 HTTP {resp.status_code}: {resp.text[:200]} "
                            f"(base_url={effective_url}, model={model_id})"
                        )
                    else:
                        data = resp.json()
                        embs = data.get("embeddings")
                        if not isinstance(embs, list) or not embs:
                            raise EmbeddingError("embedding 返回格式异常: 缺少 embeddings 字段")
                        embeddings = [[float(x) for x in vec] for vec in embs]

                    out.extend(embeddings)
                    idx += len(chunk)
        except httpx.HTTPError as e:
            hint = (
                "；请检查：1) embedding 服务是否启动 2) base_url/端口是否正确 "
                "3) 网络是否可达(容器内与宿主机不同)"
            )
            lower = effective_url.lower()
            if "localhost" in lower or "127.0.0.1" in lower:
                hint = (
                    "；若后端运行在 docker 容器中，请将 base_url 配置为 "
                    "`http://host.docker.internal:11434`(macOS/Windows) 或宿主机 IP，"
                    "不要用容器内的 localhost"
                )
            raise EmbeddingError(
                f"连接 embedding 接口失败: {type(e).__name__}: {e} "
                f"(base_url={effective_url}, model={model_id}){hint}"
            ) from e

        if len(out) != len(texts):
            raise EmbeddingError("embedding 返回条数与输入不一致")
        return out

    import httpx
    from openai import APIConnectionError, APIStatusError, AsyncOpenAI

    if not api_key:
        raise EmbeddingError("provider 未配置 api_key")

    effective_url = _normalize_openai_compatible_base_url(base_url)
    out: list[list[float]] = []
    batch = batch_size if batch_size and batch_size > 0 else DEFAULT_BATCH_SIZE
    idx = 0
    # Use an explicit httpx client to avoid OpenAI SDK internal
    # AsyncHttpxClientWrapper lifecycle issues in long-running Celery workers.
    http_client = httpx.AsyncClient(timeout=60.0)
    try:
        async with AsyncOpenAI(
            api_key=api_key,
            base_url=effective_url,
            timeout=60.0,
            http_client=http_client,
        ) as client:
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
    finally:
        await http_client.aclose()
    if len(out) != len(texts):
        raise EmbeddingError("embedding 返回条数与输入不一致")
    return out
