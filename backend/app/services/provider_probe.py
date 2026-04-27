"""按 provider 类型调上游 /models 接口,统一抽象成 list_models。

连通性测试和"可用模型"列表共用此层,避免重复调上游。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import settings

ProbeErrorKind = Literal["auth", "network", "timeout", "unknown", "config"]


@dataclass
class ProbeError(Exception):
    kind: ProbeErrorKind
    message: str
    status_code: int | None = None

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message}"


_OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"
_ANTHROPIC_BASE = "https://api.anthropic.com/v1"
_AZURE_API_VERSION = "2024-02-01"


def _strip_slash(url: str) -> str:
    return url.rstrip("/")

def _strip_ollama_v1(url: str) -> str:
    u = _strip_slash(url)
    if u.endswith("/v1"):
        return u[: -len("/v1")]
    return u


async def list_models(
    provider_type: str,
    api_key: str,
    base_url: str | None = None,
) -> list[str]:
    """返回上游可用模型 id 列表。失败抛 ProbeError。"""
    if provider_type == "openai":
        return await _openai(api_key, base_url or _OPENAI_DEFAULT_BASE)
    if provider_type == "anthropic":
        return await _anthropic(api_key, base_url or _ANTHROPIC_BASE)
    if provider_type == "azure":
        if not base_url:
            raise ProbeError("config", "base_url is required for azure provider")
        return await _azure(api_key, base_url)
    if provider_type in ("zhipu", "qwen"):
        if not base_url:
            raise ProbeError(
                "config", f"base_url is required for {provider_type} (OpenAI-compatible endpoint)"
            )
        return await _openai(api_key, base_url)
    if provider_type == "ollama":
        if not base_url:
            raise ProbeError("config", "base_url is required for ollama provider")
        return await _ollama(base_url)
    raise ProbeError("config", f"unsupported provider_type: {provider_type}")


async def _get(url: str, headers: dict[str, str]) -> httpx.Response:
    timeout = httpx.Timeout(settings.http_probe_timeout)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, headers=headers)
    except httpx.TimeoutException as e:
        raise ProbeError("timeout", f"upstream timeout: {e}") from e
    except httpx.ConnectError as e:
        raise ProbeError("network", f"connection failed: {e}") from e
    except httpx.HTTPError as e:
        raise ProbeError("network", f"http error: {e}") from e


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code in (401, 403):
        raise ProbeError("auth", f"authentication failed: {resp.status_code}", resp.status_code)
    if resp.status_code >= 400:
        raise ProbeError(
            "unknown",
            f"upstream returned {resp.status_code}: {resp.text[:200]}",
            resp.status_code,
        )


async def _openai(api_key: str | None, base_url: str) -> list[str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = await _get(
        f"{_strip_slash(base_url)}/models",
        headers=headers,
    )
    _raise_for_status(resp)
    data = resp.json().get("data", [])
    return [item["id"] for item in data if "id" in item]

async def _ollama(base_url: str) -> list[str]:
    resp = await _get(
        f"{_strip_ollama_v1(base_url)}/api/tags",
        headers={},
    )
    _raise_for_status(resp)
    data = resp.json().get("models", [])
    return [m["name"] for m in data if isinstance(m, dict) and "name" in m]


async def _anthropic(api_key: str, base_url: str) -> list[str]:
    resp = await _get(
        f"{_strip_slash(base_url)}/models",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    _raise_for_status(resp)
    data = resp.json().get("data", [])
    return [item["id"] for item in data if "id" in item]


async def _azure(api_key: str, base_url: str) -> list[str]:
    resp = await _get(
        f"{_strip_slash(base_url)}/openai/deployments?api-version={_AZURE_API_VERSION}",
        headers={"api-key": api_key},
    )
    _raise_for_status(resp)
    data = resp.json().get("data", [])
    return [item.get("id") or item.get("model") for item in data if item]
