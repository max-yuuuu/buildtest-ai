import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ModelType = Literal["llm", "embedding", "ocr", "rerank", "vlm"]


class ModelBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str = Field(min_length=1, max_length=100)
    model_type: ModelType
    context_window: int | None = Field(default=None, gt=0)
    vector_dimension: int | None = Field(default=None, gt=0)
    embedding_batch_size: int | None = Field(default=None, gt=0, le=2048)


class ModelCreate(ModelBase):
    @model_validator(mode="after")
    def _batch_size_only_for_embedding(self) -> "ModelCreate":
        if self.model_type != "embedding" and self.embedding_batch_size is not None:
            raise ValueError("embedding_batch_size is only valid for embedding models")
        return self


class ModelUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_type: ModelType | None = None
    context_window: int | None = Field(default=None, gt=0)
    vector_dimension: int | None = Field(default=None, gt=0)
    embedding_batch_size: int | None = Field(default=None, gt=0, le=2048)


class ModelRead(ModelBase):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    provider_id: uuid.UUID
    created_at: datetime


class AvailableModel(BaseModel):
    """上游 provider 可用模型条目。is_registered 标记本地已登记,便于前端区分。"""

    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    suggested_type: ModelType | None = None
    is_registered: bool = False


class EmbeddingDimensionProbeRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=100)


class EmbeddingDimensionProbeResponse(BaseModel):
    model_id: str
    vector_dimension: int
