"""Add asset_delistings table for delisted companies

Revision ID: e3f4a5b6c7d8
Revises: d7e8f9a0b1c2
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'e3f4a5b6c7d8'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('asset_delistings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_registry_id', sa.Integer(), nullable=False),
        sa.Column('delisting_date', sa.Date(), nullable=False),
        sa.Column('delisting_price', sa.Float(), nullable=False, server_default='0'),
        sa.Column('delisting_currency', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('delisting_type', sa.String(30), nullable=False, server_default='CASH_ACQUISITION'),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['asset_registry_id'], ['asset_registry.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('asset_delistings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_asset_delistings_delisting_date'), ['delisting_date'])
        batch_op.create_index(batch_op.f('ix_asset_delistings_asset_registry_id'), ['asset_registry_id'])


def downgrade():
    with op.batch_alter_table('asset_delistings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_asset_delistings_asset_registry_id'))
        batch_op.drop_index(batch_op.f('ix_asset_delistings_delisting_date'))
    op.drop_table('asset_delistings')
