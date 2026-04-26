import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    vector_db_config_id: uuid.UUID
    embedding_model_id: uuid.UUID
    chunk_size: int = Field(default=512, ge=64, le=8192)
    chunk_overlap: int = Field(default=50, ge=0, le=4096)
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    retrieval_similarity_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    retrieval_config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def overlap_lt_chunk(self) -> Self:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        return self


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    embedding_model_id: uuid.UUID | None = None
    chunk_size: int | None = Field(default=None, ge=64, le=8192)
    chunk_overlap: int | None = Field(default=None, ge=0, le=4096)
    retrieval_top_k: int | None = Field(default=None, ge=1, le=50)
    retrieval_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieval_config: dict | None = None


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    vector_db_config_id: uuid.UUID
    collection_name: str
    embedding_model_id: uuid.UUID
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    retrieval_similarity_threshold: float
    retrieval_config: dict
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    file_name: str
    file_type: str | None
    file_size: int | None
    status: str
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    ingestion_job_id: uuid.UUID | None = None
    ingestion_job_status: str | None = None
    ingestion_attempt_count: int | None = None


class DocumentChunkRead(BaseModel):
    id: uuid.UUID
    chunk_index: int
    char_length: int
    token_length: int | None = None
    preview_text: str | None = None
    source: dict = Field(default_factory=dict)
    created_at: datetime


class DocumentChunkSummaryRead(BaseModel):
    total_chunks: int
    avg_char_length: float | None = None
    min_char_length: int | None = None
    max_char_length: int | None = None


class DocumentChunkPaginationRead(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class DocumentChunkDocumentRead(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    name: str
    status: str
    ingestion_job_id: uuid.UUID | None = None
    completed_at: datetime | None = None


class DocumentChunksResponse(BaseModel):
    document: DocumentChunkDocumentRead
    chunk_summary: DocumentChunkSummaryRead
    pagination: DocumentChunkPaginationRead
    items: list[DocumentChunkRead]


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    attempt_count: int
    max_retries: int
    error_message: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    strategy_id: str | None = Field(default=None, min_length=1, max_length=64)
    top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class RetrieveHit(BaseModel):
    knowledge_base_id: uuid.UUID | None = None
    document_id: uuid.UUID
    chunk_index: int
    text: str
    score: float
    source: dict | None = None


class RetrieveResponse(BaseModel):
    hits: list[RetrieveHit]
    strategy_id: str | None = None
    retrieval_params: dict = Field(default_factory=dict)


class RebuildRequest(BaseModel):
    document_id: uuid.UUID | None = None
