"""Add CryptoPriceVerification table for price checking

Revision ID: 7646dc55e408
Revises: 
Create Date: 2025-05-22 16:30:36.581477

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7646dc55e408'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    #op.create_table('crypto_price_verifications',
    #sa.Column('id', sa.Integer(), nullable=False),
    #sa.Column('user_id', sa.Integer(), nullable=False),
    #sa.Column('currency_symbol', sa.String(length=20), nullable=False),
    #sa.Column('price_available', sa.Boolean(), nullable=False),
    #sa.Column('last_check', sa.DateTime(), nullable=True),
    #sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    #sa.PrimaryKeyConstraint('id'),
    #sa.UniqueConstraint('user_id', 'currency_symbol', name='unique_user_currency')
    #)
    pass
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    #op.drop_table('crypto_price_verifications')
    pass
    # ### end Alembic commands ###
