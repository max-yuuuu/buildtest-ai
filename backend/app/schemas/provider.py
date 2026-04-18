import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderType = Literal["openai", "anthropic", "azure", "zhipu", "qwen"]


class ProviderBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: ProviderType
    base_url: str | None = None
    is_active: bool = True


class ProviderCreate(ProviderBase):
    api_key: str = Field(min_length=1)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = None
    base_url: str | None = None
    is_active: bool | None = None


class ProviderRead(ProviderBase):
    """对外暴露的视图,不返回明文 api_key,只返回 mask。"""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    api_key_mask: str
    created_at: datetime
    updated_at: datetime


class ProviderTestResult(BaseModel):
    """连通性测试结果。ok=False 仍返回 200,HTTP 错误码只用于 provider 不存在 / 未授权。"""

    ok: bool
    latency_ms: int
    message: str
    models: list[str] = Field(default_factory=list)


def mask_api_key(plain: str) -> str:
    if len(plain) <= 8:
        return "***"
    return f"{plain[:4]}...{plain[-4:]}"
