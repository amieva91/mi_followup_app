"""add yahoo finance fields to assets

Revision ID: a9ef77389298
Revises: ba500a563900
Create Date: 2025-11-03 17:23:01.501380

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9ef77389298'
down_revision = 'ba500a563900'
branch_labels = None
depends_on = None


def upgrade():
    # PRECIOS Y CAMBIOS
    # current_price, previous_close, day_change_percent, last_price_update ya existen - no añadir
    
    # VALORACIÓN
    op.add_column('assets', sa.Column('market_cap', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('market_cap_formatted', sa.String(20), nullable=True))
    op.add_column('assets', sa.Column('market_cap_eur', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('trailing_pe', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('forward_pe', sa.Float(), nullable=True))
    
    # INFORMACIÓN CORPORATIVA
    # sector ya existe - no añadir
    op.add_column('assets', sa.Column('industry', sa.String(100), nullable=True))
    
    # RIESGO Y RENDIMIENTO
    op.add_column('assets', sa.Column('beta', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('dividend_rate', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('dividend_yield', sa.Float(), nullable=True))
    
    # ANÁLISIS DE MERCADO
    op.add_column('assets', sa.Column('recommendation_key', sa.String(20), nullable=True))
    op.add_column('assets', sa.Column('number_of_analyst_opinions', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('target_mean_price', sa.Float(), nullable=True))


def downgrade():
    # Eliminar columnas en orden inverso (solo las que esta migración añadió)
    op.drop_column('assets', 'target_mean_price')
    op.drop_column('assets', 'number_of_analyst_opinions')
    op.drop_column('assets', 'recommendation_key')
    op.drop_column('assets', 'dividend_yield')
    op.drop_column('assets', 'dividend_rate')
    op.drop_column('assets', 'beta')
    op.drop_column('assets', 'industry')
    # sector ya existía - no eliminar
    op.drop_column('assets', 'forward_pe')
    op.drop_column('assets', 'trailing_pe')
    op.drop_column('assets', 'market_cap_eur')
    op.drop_column('assets', 'market_cap_formatted')
    op.drop_column('assets', 'market_cap')
    # current_price, previous_close, day_change_percent, last_price_update ya existían - no eliminar
