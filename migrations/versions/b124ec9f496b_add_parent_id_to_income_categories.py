"""add parent_id to income_categories

Revision ID: b124ec9f496b
Revises: a1b2c3d4e5f6
Create Date: 2026-02-08 21:15:59.309778

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b124ec9f496b'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('income_categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_income_categories_parent_id', 'income_categories', ['parent_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('income_categories', schema=None) as batch_op:
        batch_op.drop_constraint('fk_income_categories_parent_id', type_='foreignkey')
        batch_op.drop_column('parent_id')

    # ### end Alembic commands ###
