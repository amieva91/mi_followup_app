"""add analyst_consensus_updated_at to assets

Revision ID: x9y8z7w6v5u4
Revises: wlmanual01
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa


revision = "x9y8z7w6v5u4"
down_revision = "wlmanual01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assets",
        sa.Column("analyst_consensus_updated_at", sa.DateTime(), nullable=True),
    )
    # Evita un re-fetch masivo el primer día: aproximar con updated_at si ya hay datos de consenso
    op.execute(
        """
        UPDATE assets
        SET analyst_consensus_updated_at = updated_at
        WHERE analyst_consensus_updated_at IS NULL
          AND (
            recommendation_key IS NOT NULL
            OR number_of_analyst_opinions IS NOT NULL
            OR target_mean_price IS NOT NULL
          )
        """
    )


def downgrade():
    op.drop_column("assets", "analyst_consensus_updated_at")
