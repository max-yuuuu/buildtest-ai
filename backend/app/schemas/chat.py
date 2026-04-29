import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ChatMode = Literal["quick", "agent", "data"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    mode: ChatMode = "quick"
    knowledge_base_ids: list[uuid.UUID] = Field(min_length=1)

    @field_validator("knowledge_base_ids")
    @classmethod
    def dedupe_knowledge_base_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        seen: set[uuid.UUID] = set()
        unique_ids: list[uuid.UUID] = []
        for kb_id in value:
            if kb_id in seen:
                continue
            seen.add(kb_id)
            unique_ids.append(kb_id)
        return unique_ids


class ChatAcceptedResponse(BaseModel):
    mode: ChatMode
    status: str = "completed"
    answer: str
    citations: list[dict] = Field(default_factory=list)
    citation_mappings: list[dict] = Field(default_factory=list)
    attempts: list[dict] = Field(default_factory=list)
