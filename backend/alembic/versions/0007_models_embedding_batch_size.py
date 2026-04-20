"""models 表新增 embedding_batch_size 字段

阿里云 DashScope text-embedding-v3/v4 单次请求最多 10 个 input,
OpenAI 则可到 2048。不同 provider/model 差异较大,放在 model 级而非 client 硬编码。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_models_embedding_batch_size"
down_revision: str | None = "0006_kb_nullable_embedding_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "models",
        sa.Column("embedding_batch_size", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("models", "embedding_batch_size")
