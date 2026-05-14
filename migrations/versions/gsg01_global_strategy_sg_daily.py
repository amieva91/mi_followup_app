"""global_strategy_sg_daily: serie SG por usuario (día UTC)

Revision ID: gsg01
Revises: wluserpricetgt01
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa


revision = "gsg01"
down_revision = "wluserpricetgt01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "global_strategy_sg_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("sg", sa.Float(), nullable=False),
        sa.Column("s_us", sa.Float(), nullable=True),
        sa.Column("s_eu", sa.Float(), nullable=True),
        sa.Column("s_as", sa.Float(), nullable=True),
        sa.Column("indicator_as_of", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "snapshot_date", name="uq_global_strategy_sg_user_day"),
    )
    op.create_index(
        op.f("ix_global_strategy_sg_daily_user_id"),
        "global_strategy_sg_daily",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_global_strategy_sg_daily_snapshot_date"),
        "global_strategy_sg_daily",
        ["snapshot_date"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_global_strategy_sg_daily_snapshot_date"), table_name="global_strategy_sg_daily")
    op.drop_index(op.f("ix_global_strategy_sg_daily_user_id"), table_name="global_strategy_sg_daily")
    op.drop_table("global_strategy_sg_daily")
