import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KbModelPurpose = Literal["embedding", "llm", "rerank", "vlm"]


class KnowledgeBaseModelConfigUpsert(BaseModel):
    purpose: KbModelPurpose
    model_id: uuid.UUID


class KnowledgeBaseModelConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    knowledge_base_id: uuid.UUID
    purpose: KbModelPurpose
    model_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentModelConfigUpsert(BaseModel):
    model_id: uuid.UUID


class AgentModelConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: str = Field(min_length=1, max_length=64)
    model_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
