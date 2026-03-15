"""add_user_login_log_table

Revision ID: e5f6a7b8c9d0
Revises: 7a6d787c3ac4
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = '7a6d787c3ac4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_login_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('logged_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_login_log_logged_at'), 'user_login_log', ['logged_at'], unique=False)
    op.create_index(op.f('ix_user_login_log_user_id'), 'user_login_log', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_user_login_log_user_id'), table_name='user_login_log')
    op.drop_index(op.f('ix_user_login_log_logged_at'), table_name='user_login_log')
    op.drop_table('user_login_log')
