import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import EncryptedString


class VectorDbConfig(Base):
    __tablename__ = "vector_db_configs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)
    connection_string: Mapped[str] = mapped_column(EncryptedString(4096), nullable=False)
    connection_string_mask: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(EncryptedString(1024), nullable=True)
    api_key_mask: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
