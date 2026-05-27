"""Add recurrence contract pause/resume columns to expenses and incomes

Revision ID: reccontract01
Revises: gsmacro01
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = 'reccontract01'
down_revision = 'gsmacro01'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'recurrence_early_terminated',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column('recurrence_original_end_date', sa.Date(), nullable=True)
        )

    with op.batch_alter_table('incomes', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'recurrence_early_terminated',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column('recurrence_original_end_date', sa.Date(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('incomes', schema=None) as batch_op:
        batch_op.drop_column('recurrence_original_end_date')
        batch_op.drop_column('recurrence_early_terminated')

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('recurrence_original_end_date')
        batch_op.drop_column('recurrence_early_terminated')
