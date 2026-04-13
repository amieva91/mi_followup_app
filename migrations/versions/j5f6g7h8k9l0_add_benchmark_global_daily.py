"""benchmark global daily series + state version

Revision ID: j5f6g7h8k9l0
Revises: i4e5f6g7h8j9
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa


revision = "j5f6g7h8k9l0"
down_revision = "i4e5f6g7h8j9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "benchmark_global_daily",
        sa.Column("benchmark_name", sa.String(length=128), nullable=False),
        sa.Column("yahoo_ticker", sa.String(length=64), nullable=False),
        sa.Column("data_points", sa.JSON(), nullable=False),
        sa.Column("hist_end_date", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("benchmark_name"),
    )
    op.create_table(
        "benchmark_global_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("daily_data_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(sa.text("INSERT INTO benchmark_global_state (id, daily_data_version) VALUES (1, 0)"))


def downgrade():
    op.drop_table("benchmark_global_state")
    op.drop_table("benchmark_global_daily")
