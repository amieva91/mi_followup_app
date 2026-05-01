"""add delivery_mode and delivery_phase_status to company_reports

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-01

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company_reports",
        sa.Column("delivery_mode", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "company_reports",
        sa.Column("delivery_phase_status", sa.String(length=20), nullable=True),
    )


def downgrade():
    op.drop_column("company_reports", "delivery_phase_status")
    op.drop_column("company_reports", "delivery_mode")
