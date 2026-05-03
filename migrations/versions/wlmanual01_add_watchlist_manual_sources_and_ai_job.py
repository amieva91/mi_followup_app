"""watchlist manual_field_sources + watchlist_ai_jobs

Revision ID: wlmanual01
Revises: r8s9t0u1v2w3
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa


revision = "wlmanual01"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("manual_field_sources", sa.JSON(), nullable=True)
        )

    op.create_table(
        "watchlist_ai_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_asset_id", sa.Integer(), nullable=True),
        sa.Column("current_asset_label", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["current_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_watchlist_ai_jobs_user_id", "watchlist_ai_jobs", ["user_id"], unique=False
    )
    op.create_index(
        "ix_watchlist_ai_jobs_status", "watchlist_ai_jobs", ["status"], unique=False
    )


def downgrade():
    op.drop_index("ix_watchlist_ai_jobs_status", table_name="watchlist_ai_jobs")
    op.drop_index("ix_watchlist_ai_jobs_user_id", table_name="watchlist_ai_jobs")
    op.drop_table("watchlist_ai_jobs")
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.drop_column("manual_field_sources")
