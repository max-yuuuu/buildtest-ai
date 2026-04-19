import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vector_db_config_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("vector_db_configs.id", ondelete="RESTRICT"), nullable=False
    )
    collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 软删时置 NULL 以释放对 models 的引用,便于取消模型登记；未删库必须非空(由业务保证)
    embedding_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("models.id", ondelete="RESTRICT"), nullable=True
    )
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    retrieval_similarity_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7
    )
    retrieval_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
