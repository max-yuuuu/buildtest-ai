import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeBaseModelConfig(Base):
    __tablename__ = "knowledge_base_model_configs"
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "purpose", name="uq_kb_model_configs_kb_purpose"),
        CheckConstraint(
            "purpose IN ('embedding', 'llm', 'rerank', 'vlm')",
            name="ck_kb_model_configs_purpose",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AgentModelConfig(Base):
    __tablename__ = "agent_model_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", name="uq_agent_model_configs_user_agent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
