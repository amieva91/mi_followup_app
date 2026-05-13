"""watchlist: precio objetivo personal opcional (usuario)

Revision ID: wluserpricetgt01
Revises: wlcomments01
Create Date: 2026-05-11

Independiente de target_price_5yr (calculado por la app).
"""

from alembic import op
import sqlalchemy as sa


revision = "wluserpricetgt01"
down_revision = "wlcomments01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("user_price_target", sa.Float(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.drop_column("user_price_target")
