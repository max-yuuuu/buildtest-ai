"""vector_db_configs table"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_vector_db_configs"
down_revision: str | None = "0003_models_unique_model_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vector_db_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("db_type", sa.String(50), nullable=False),
        sa.Column("connection_string", sa.String(4096), nullable=False),
        sa.Column("connection_string_mask", sa.String(255), nullable=False),
        sa.Column("api_key_encrypted", sa.String(1024), nullable=True),
        sa.Column("api_key_mask", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_vector_db_configs_user_id", "vector_db_configs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_vector_db_configs_user_id", table_name="vector_db_configs")
    op.drop_table("vector_db_configs")
