"""global_strategy_macro_daily: cierres diarios Yahoo para motor SG macro

Revision ID: gsmacro01
Revises: gsg01
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa


revision = "gsmacro01"
down_revision = "gsg01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "global_strategy_macro_daily",
        sa.Column("series_key", sa.String(length=32), nullable=False),
        sa.Column("yahoo_ticker", sa.String(length=64), nullable=False),
        sa.Column("data_points", sa.JSON(), nullable=False),
        sa.Column("hist_end_date", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("series_key"),
    )
    op.create_table(
        "global_strategy_macro_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.Column("usa_score_mode", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO global_strategy_macro_state (id, data_version, usa_score_mode, updated_at) "
        "VALUES (1, 0, 'vix', datetime('now'))"
    )


def downgrade():
    op.drop_table("global_strategy_macro_state")
    op.drop_table("global_strategy_macro_daily")
