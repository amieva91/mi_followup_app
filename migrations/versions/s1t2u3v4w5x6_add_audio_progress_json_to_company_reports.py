"""add audio_progress_json to company_reports

Revision ID: s1t2u3v4w5x6
Revises: r8s9t0u1v2w3
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa


revision = "s1t2u3v4w5x6"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("audio_progress_json", sa.Text(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.drop_column("audio_progress_json")
