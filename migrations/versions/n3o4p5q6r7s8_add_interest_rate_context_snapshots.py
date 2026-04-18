"""add interest_rate_context_snapshots

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa


revision = "n3o4p5q6r7s8"
down_revision = "m2n3o4p5q6r7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interest_rate_context_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("bce_euribor_12m_percent", sa.Numeric(12, 6), nullable=True),
        sa.Column("bce_time_period", sa.String(length=16), nullable=True),
        sa.Column("yahoo_esr_f_price", sa.Numeric(14, 6), nullable=True),
        sa.Column("yahoo_implied_percent", sa.Numeric(12, 6), nullable=True),
        sa.Column("spread_implied_minus_bce", sa.Numeric(12, 6), nullable=True),
        sa.Column("trend_label", sa.String(length=32), nullable=False),
        sa.Column("bce_fetch_error", sa.String(length=512), nullable=True),
        sa.Column("yahoo_fetch_error", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interest_rate_context_snapshots_fetched_at"),
        "interest_rate_context_snapshots",
        ["fetched_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_interest_rate_context_snapshots_fetched_at"),
        table_name="interest_rate_context_snapshots",
    )
    op.drop_table("interest_rate_context_snapshots")
