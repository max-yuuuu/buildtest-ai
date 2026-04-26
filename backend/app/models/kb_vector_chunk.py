import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, TypeDecorator, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.types import JSON, UserDefinedType

from app.core.database import Base


class _PgVectorType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        _ = kw
        return "vector"


class _VectorDbType(TypeDecorator):
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect) -> TypeEngine:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgVectorType())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: list[float] | None, dialect):
        if value is None:
            return None
        return "[" + ",".join(str(float(item)) for item in value) + "]"

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if isinstance(value, list):
            return [float(item) for item in value]
        raw = str(value).strip()
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        if not raw:
            return []
        return [float(item) for item in raw.split(",")]


class KbVectorChunk(Base):
    """仅 postgres_pgvector 路径写入；Qdrant 数据在独立 collection。"""

    __tablename__ = "kb_vector_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(_VectorDbType(), nullable=False)
    token_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
