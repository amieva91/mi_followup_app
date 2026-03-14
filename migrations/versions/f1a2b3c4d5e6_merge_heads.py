"""merge heads (fix_health_detail + price_update_failed_at)

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0, fix_health_detail_001
Create Date: 2026-03-14

"""
from alembic import op


revision = 'f1a2b3c4d5e6'
down_revision = ('e5f6a7b8c9d0', 'fix_health_detail_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
