"""Remove account_number from broker_accounts

Revision ID: f8a9b0c1d2e3
Revises: e3f4a5b6c7d8
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'f8a9b0c1d2e3'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('broker_accounts', schema=None) as batch_op:
        batch_op.drop_column('account_number')


def downgrade():
    with op.batch_alter_table('broker_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_number', sa.String(length=50), nullable=True))

