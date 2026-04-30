"""add queue + email status to company_reports

Revision ID: ae3b7c1d2f90
Revises: s1t2u3v4w5x6
Create Date: 2026-04-30

"""

from alembic import op
import sqlalchemy as sa


revision = "ae3b7c1d2f90"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("report_enqueued_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("audio_enqueued_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("email_status", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("email_error_msg", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("email_completed_at", sa.DateTime(), nullable=True))

    # Backfill: queue timestamps default to created_at for existing rows.
    op.execute(
        """
        UPDATE company_reports
        SET report_enqueued_at = COALESCE(report_enqueued_at, created_at)
        WHERE report_enqueued_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE company_reports
        SET audio_enqueued_at = COALESCE(audio_enqueued_at, created_at)
        WHERE audio_enqueued_at IS NULL AND audio_status IN ('queued','processing')
        """
    )


def downgrade():
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.drop_column("email_completed_at")
        batch_op.drop_column("email_error_msg")
        batch_op.drop_column("email_status")
        batch_op.drop_column("audio_enqueued_at")
        batch_op.drop_column("report_enqueued_at")

