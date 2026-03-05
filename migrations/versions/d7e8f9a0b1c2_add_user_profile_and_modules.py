"""Add user profile (avatar, birth_year) and enabled_modules

Revision ID: d7e8f9a0b1c2
Revises: 0154d7bbbbb1
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa


revision = 'd7e8f9a0b1c2'
down_revision = 'fix_health_detail_001'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('avatar_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('birth_year', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('enabled_modules', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('enabled_modules')
        batch_op.drop_column('birth_year')
        batch_op.drop_column('avatar_id')
