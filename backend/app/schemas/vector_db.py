import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VectorDbType = Literal[
    "postgres_pgvector",
    "qdrant",
    "milvus",
    "weaviate",
    "pinecone",
    "chroma",
]


def mask_connection_string(plain: str) -> str:
    from urllib.parse import urlparse

    raw = plain.strip()
    if not raw:
        return "***"
    u = urlparse(raw)
    if u.hostname:
        scheme = f"{u.scheme}://" if u.scheme else ""
        port = f":{u.port}" if u.port else ""
        return f"{scheme}***@{u.hostname}{port}"
    if len(raw) <= 16:
        return "***"
    return f"{raw[:6]}...{raw[-4:]}"


def mask_api_key_optional(plain: str | None) -> str | None:
    if not plain:
        return None
    if len(plain) <= 8:
        return "***"
    return f"{plain[:4]}...{plain[-4:]}"


class VectorDbBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    db_type: VectorDbType
    is_active: bool = True


class VectorDbCreate(VectorDbBase):
    connection_string: str = Field(min_length=1, max_length=4000)
    api_key: str | None = Field(default=None, max_length=2000)


class VectorDbUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    connection_string: str | None = Field(default=None, min_length=1, max_length=4000)
    api_key: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class VectorDbRead(VectorDbBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    connection_string_mask: str
    api_key_mask: str | None = None
    created_at: datetime
    updated_at: datetime


class VectorDbTestResult(BaseModel):
    ok: bool
    latency_ms: int
    message: str
