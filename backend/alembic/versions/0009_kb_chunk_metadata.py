"""add token length and source metadata for kb chunks"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_kb_chunk_metadata"
down_revision: str | None = "0008_ingestion_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kb_vector_chunks", sa.Column("token_length", sa.Integer(), nullable=True))
    op.add_column(
        "kb_vector_chunks",
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("kb_vector_chunks", "source_metadata")
    op.drop_column("kb_vector_chunks", "token_length")
