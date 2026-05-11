"""watchlist general: márgenes FCF y BN sobre ventas (%)

Revision ID: wlfcfmargin01
Revises: wlreitcov01
Create Date: 2026-05-09

Ratio FCF/BN efectivo = fcf_margin_pct / net_income_margin_pct cuando ambos existen
y el denominador no es cero; si no, se usa fcf_to_net_income (legado).
"""

from alembic import op
import sqlalchemy as sa


revision = "wlfcfmargin01"
down_revision = "wlreitcov01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fcf_margin_pct", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("net_income_margin_pct", sa.Float(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.drop_column("net_income_margin_pct")
        batch_op.drop_column("fcf_margin_pct")
