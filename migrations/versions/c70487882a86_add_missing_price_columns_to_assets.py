"""add missing price columns to assets

Revision ID: c70487882a86
Revises: 3bb7be7c8afa
Create Date: 2025-12-10 16:40:13.123122

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c70487882a86'
down_revision = '3bb7be7c8afa'
branch_labels = None
depends_on = None


def upgrade():
    # Añadir columnas de precios que faltan en la tabla assets
    # Estas columnas son necesarias para el modelo Asset pero no estaban en la BD
    op.add_column('assets', sa.Column('current_price', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('previous_close', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('day_change_percent', sa.Float(), nullable=True))


def downgrade():
    # Eliminar las columnas añadidas
    op.drop_column('assets', 'day_change_percent')
    op.drop_column('assets', 'previous_close')
    op.drop_column('assets', 'current_price')
