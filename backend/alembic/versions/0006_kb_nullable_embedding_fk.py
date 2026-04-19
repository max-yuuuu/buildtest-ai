"""软删知识库时释放 embedding_model_id 外键,便于取消模型登记"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_kb_nullable_embedding_fk"
down_revision: str | None = "0005_knowledge_bases_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 须先 DROP NOT NULL,否则 UPDATE 置 NULL 会违反约束
    op.alter_column(
        "knowledge_bases",
        "embedding_model_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.execute(
        sa.text("UPDATE knowledge_bases SET embedding_model_id = NULL WHERE deleted_at IS NOT NULL")
    )


def downgrade() -> None:
    raise NotImplementedError(
        "0006 不可逆：embedding_model_id 曾为 NULL 的软删知识库无法自动恢复合法外键"
    )
