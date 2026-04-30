"""add email auth columns and verification_codes table"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_email_auth"
down_revision: str | None = "0011_notifications_center"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "verification_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verification_codes_email", "verification_codes", ["email"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_verification_codes_email", table_name="verification_codes")
    op.drop_table("verification_codes")
    op.drop_column("users", "password_hash")
