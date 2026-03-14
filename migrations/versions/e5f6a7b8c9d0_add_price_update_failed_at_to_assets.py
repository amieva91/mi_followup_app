"""add price_update_failed_at to assets for error indicator

Revision ID: e5f6a7b8c9d0
Revises: b7c8d9e0f1a2
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('price_update_failed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.drop_column('price_update_failed_at')
