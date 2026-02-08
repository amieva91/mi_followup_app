"""Add debt_plans table, debt_plan_id to expenses, debt_limit_percent to users

Revision ID: a1b2c3d4e5f6
Revises: e24b416bfe26
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'e24b416bfe26'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'debt_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('months', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['expense_categories.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('debt_limit_percent', sa.Float(), nullable=True))

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('debt_plan_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_expenses_debt_plan', 'debt_plans', ['debt_plan_id'], ['id'])


def downgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_constraint('fk_expenses_debt_plan', type_='foreignkey')
        batch_op.drop_column('debt_plan_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('debt_limit_percent')

    op.drop_table('debt_plans')
