import uuid
from typing import Literal

from pydantic import BaseModel, Field


ChatMode = Literal["quick", "agent", "data"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    mode: ChatMode = "quick"
    knowledge_base_id: uuid.UUID


class ChatAcceptedResponse(BaseModel):
    mode: ChatMode
    status: str = "completed"
    answer: str
    citations: list[dict] = Field(default_factory=list)
    citation_mappings: list[dict] = Field(default_factory=list)
    attempts: list[dict] = Field(default_factory=list)
