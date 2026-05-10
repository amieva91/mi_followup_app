"""watchlist REIT: FFO interest coverage y FFO/total debt para F_RE

Revision ID: wlreitcov01
Revises: wlvalplan01
Create Date: 2026-05-09

Coberturas según plan §14.E (media geométrica en watchlist_reit_valuation).
"""

from alembic import op
import sqlalchemy as sa


revision = "wlreitcov01"
down_revision = "wlvalplan01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ffo_interest_coverage", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ffo_to_total_debt", sa.Float(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.drop_column("ffo_to_total_debt")
        batch_op.drop_column("ffo_interest_coverage")
