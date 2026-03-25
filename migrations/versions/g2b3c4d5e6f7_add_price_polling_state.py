"""Add price_polling_state table

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2025-03-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'g2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'price_polling_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('last_asset_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated_asset_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['last_updated_asset_id'], ['assets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # Solo 1 fila: id=1
    op.execute(sa.text("INSERT INTO price_polling_state (id, last_asset_index) VALUES (1, 0)"))


def downgrade():
    op.drop_table('price_polling_state')
