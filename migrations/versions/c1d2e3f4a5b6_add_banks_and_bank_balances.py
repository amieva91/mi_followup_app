"""add banks and bank_balances tables

Revision ID: c1d2e3f4a5b6
Revises: b124ec9f496b
Create Date: 2026-02-29

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'b124ec9f496b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'banks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('icon', sa.String(10), nullable=True),
        sa.Column('color', sa.String(20), server_default='blue', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_banks_user_id', 'banks', ['user_id'])

    op.create_table(
        'bank_balances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('bank_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['bank_id'], ['banks.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bank_id', 'year', 'month', name='uq_bank_balance_per_month')
    )
    op.create_index('ix_bank_balances_user_id', 'bank_balances', ['user_id'])
    op.create_index('ix_bank_balances_bank_year_month', 'bank_balances', ['bank_id', 'year', 'month'])


def downgrade():
    op.drop_table('bank_balances')
    op.drop_table('banks')
