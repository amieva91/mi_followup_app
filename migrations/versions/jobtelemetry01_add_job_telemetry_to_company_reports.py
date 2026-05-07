"""add job telemetry columns to company_reports

Revision ID: jobtelemetry01
Revises: x9y8z7w6v5u4
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "jobtelemetry01"
down_revision = "x9y8z7w6v5u4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_reports", sa.Column("job_kind", sa.String(length=40), nullable=True))
    op.add_column("company_reports", sa.Column("job_status", sa.String(length=20), nullable=True))
    op.add_column("company_reports", sa.Column("job_phase", sa.String(length=40), nullable=True))
    op.add_column("company_reports", sa.Column("job_started_at", sa.DateTime(), nullable=True))
    op.add_column("company_reports", sa.Column("job_finished_at", sa.DateTime(), nullable=True))

    op.add_column("company_reports", sa.Column("provider_last_status", sa.String(length=40), nullable=True))
    op.add_column("company_reports", sa.Column("provider_last_poll_at", sa.DateTime(), nullable=True))
    op.add_column("company_reports", sa.Column("provider_poll_count", sa.Integer(), nullable=True))
    op.add_column("company_reports", sa.Column("provider_last_http_status", sa.Integer(), nullable=True))
    op.add_column("company_reports", sa.Column("provider_last_error_kind", sa.String(length=40), nullable=True))
    op.add_column("company_reports", sa.Column("provider_last_error_msg", sa.Text(), nullable=True))
    op.add_column("company_reports", sa.Column("provider_create_attempt", sa.Integer(), nullable=True))
    op.add_column("company_reports", sa.Column("provider_next_retry_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("company_reports", "provider_next_retry_at")
    op.drop_column("company_reports", "provider_create_attempt")
    op.drop_column("company_reports", "provider_last_error_msg")
    op.drop_column("company_reports", "provider_last_error_kind")
    op.drop_column("company_reports", "provider_last_http_status")
    op.drop_column("company_reports", "provider_poll_count")
    op.drop_column("company_reports", "provider_last_poll_at")
    op.drop_column("company_reports", "provider_last_status")

    op.drop_column("company_reports", "job_finished_at")
    op.drop_column("company_reports", "job_started_at")
    op.drop_column("company_reports", "job_phase")
    op.drop_column("company_reports", "job_status")
    op.drop_column("company_reports", "job_kind")

