"""migrate kb_vector_chunks.embedding to pgvector"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_kb_chunks_pgvector_native"
down_revision: str | None = "0009_kb_chunk_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.execute(
        sa.text(
            """
            ALTER TABLE kb_vector_chunks
            ALTER COLUMN embedding TYPE vector
            USING embedding::text::vector
            """
        )
    )
    # NOTE:
    # 这里不在 Alembic 迁移事务内创建 ivfflat 索引。
    # 原因：
    # 1) vector 为可变维度时需要按维度建 expression/partial index；
    # 2) CREATE INDEX 在本迁移事务下容易触发 "ObjectInUse"。
    # 索引请在迁移完成后由运维脚本单独执行（必要时使用 CONCURRENTLY）。


def downgrade() -> None:
    # 与 upgrade 对应：本迁移不负责索引生命周期，仅回退列类型。
    op.execute(
        sa.text(
            """
            ALTER TABLE kb_vector_chunks
            ALTER COLUMN embedding TYPE jsonb
            USING embedding::text::jsonb
            """
        )
    )
