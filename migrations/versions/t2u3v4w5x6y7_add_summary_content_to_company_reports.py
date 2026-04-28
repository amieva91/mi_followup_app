"""add summary_content to company_reports

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa


revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("summary_content", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.drop_column("summary_content")
