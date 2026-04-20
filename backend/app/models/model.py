import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Model(Base):
    """Provider 下挂载的具体模型(llm / embedding)。

    evaluation_jobs.llm_model_id 与 knowledge_bases.embedding_model_id
    都指向本表;删除 provider 前必须确保无 Model 引用(级联 CASCADE 仅是兜底)。
    """

    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_models_provider_model_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # embedding 接口单次 input 条数上限;None 表示使用 client 默认(64)。
    # 例:阿里云 DashScope text-embedding-v3/v4 硬限 10,OpenAI 可到 2048。
    embedding_batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
