"""add_model_config_tables

Revision ID: 0013_add_model_config_tables
Revises: 0012_model_configs
Create Date: 2026-04-30 00:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_add_model_config_tables"
down_revision = "0012_model_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_model_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('embedding', 'llm', 'rerank', 'vlm')",
            name="ck_kb_model_configs_purpose",
        ),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_base_id", "purpose", name="uq_kb_model_configs_kb_purpose"),
    )
    op.create_index(
        op.f("ix_knowledge_base_model_configs_knowledge_base_id"),
        "knowledge_base_model_configs",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_base_model_configs_model_id"),
        "knowledge_base_model_configs",
        ["model_id"],
        unique=False,
    )

    op.create_table(
        "agent_model_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "agent_id", name="uq_agent_model_configs_user_agent"),
    )
    op.create_index(op.f("ix_agent_model_configs_user_id"), "agent_model_configs", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_model_configs_model_id"), "agent_model_configs", ["model_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_model_configs_model_id"), table_name="agent_model_configs")
    op.drop_index(op.f("ix_agent_model_configs_user_id"), table_name="agent_model_configs")
    op.drop_table("agent_model_configs")

    op.drop_index(op.f("ix_knowledge_base_model_configs_model_id"), table_name="knowledge_base_model_configs")
    op.drop_index(
        op.f("ix_knowledge_base_model_configs_knowledge_base_id"),
        table_name="knowledge_base_model_configs",
    )
    op.drop_table("knowledge_base_model_configs")
