"""add reconciliation_adjustment_metric_prefs

Revision ID: m2n3o4p5q6r7
Revises: k1l2m3n4o5p6
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa


revision = "m2n3o4p5q6r7"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reconciliation_adjustment_metric_prefs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("include_in_metrics", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "month", name="uq_recon_adj_metric_user_ym"),
    )
    op.create_index(
        op.f("ix_reconciliation_adjustment_metric_prefs_user_id"),
        "reconciliation_adjustment_metric_prefs",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_reconciliation_adjustment_metric_prefs_user_id"),
        table_name="reconciliation_adjustment_metric_prefs",
    )
    op.drop_table("reconciliation_adjustment_metric_prefs")
