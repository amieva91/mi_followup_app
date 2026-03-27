"""add_cache_rebuild_state

Revision ID: h3c4d5e6f7g8
Revises: g2b3c4d5e6f7
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa


revision = "h3c4d5e6f7g8"
down_revision = "g2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cache_rebuild_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("pending_full_history", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("pending_now", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_cache_rebuild_state_user_id"), "cache_rebuild_state", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_cache_rebuild_state_user_id"), table_name="cache_rebuild_state")
    op.drop_table("cache_rebuild_state")
