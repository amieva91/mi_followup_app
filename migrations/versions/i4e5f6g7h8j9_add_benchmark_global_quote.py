"""add benchmark_global_quote for index poll NOW cache

Revision ID: i4e5f6g7h8j9
Revises: h3c4d5e6f7g8
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa


revision = "i4e5f6g7h8j9"
down_revision = "h3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "benchmark_global_quote",
        sa.Column("benchmark_name", sa.String(length=128), nullable=False),
        sa.Column("yahoo_ticker", sa.String(length=64), nullable=False),
        sa.Column("regular_market_price", sa.Float(), nullable=True),
        sa.Column("previous_close", sa.Float(), nullable=True),
        sa.Column("day_change_percent", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("benchmark_name"),
    )


def downgrade():
    op.drop_table("benchmark_global_quote")
