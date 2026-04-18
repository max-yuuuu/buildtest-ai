"""provider api_key_mask column + models table

Revision ID: 0002_provider_mask_and_models
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_provider_mask_and_models"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_masks() -> None:
    """遍历已有 providers,解密一次 api_key 算出真实 mask 回填。

    Why:api_key_mask 设计为入库前从明文派生并单独存列,避免读路径每次解密。
    旧数据只有密文,需要一次性回填,之后不再需要解密来取 mask。
    """

    from app.core.security import decrypt
    from app.schemas.provider import mask_api_key

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, api_key_encrypted FROM providers")).fetchall()
    for row in rows:
        try:
            plain = decrypt(row.api_key_encrypted)
        except ValueError:
            # 历史脏数据:用占位符,避免阻塞迁移;运维侧后续手动清理。
            mask = "***...***"
        else:
            mask = mask_api_key(plain)
        bind.execute(
            sa.text("UPDATE providers SET api_key_mask = :m WHERE id = :i"),
            {"m": mask, "i": row.id},
        )


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column(
            "api_key_mask",
            sa.String(64),
            nullable=False,
            server_default="***...***",
        ),
    )
    _backfill_masks()
    # 清掉 server_default,未来全部由应用层(mask_api_key)填充,避免默认值掩盖 bug。
    op.alter_column("providers", "api_key_mask", server_default=None)

    op.create_table(
        "models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("context_window", sa.Integer, nullable=True),
        sa.Column("vector_dimension", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_models_provider_id", "models", ["provider_id"])


def downgrade() -> None:
    op.drop_index("ix_models_provider_id", table_name="models")
    op.drop_table("models")
    op.drop_column("providers", "api_key_mask")
