"""models table: unique (provider_id, model_id)

Revision ID: 0003_models_unique_model_id
Revises: 0002_provider_mask_and_models
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_models_unique_model_id"
down_revision: str | None = "0002_provider_mask_and_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_models_provider_model_id",
        "models",
        ["provider_id", "model_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_models_provider_model_id", table_name="models")
