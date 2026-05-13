"""watchlist: tabla de comentarios por fila (fecha/hora, edición)

Revision ID: wlcomments01
Revises: wlfcfmargin01
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "wlcomments01"
down_revision = "wlfcfmargin01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "watchlist_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlist.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_watchlist_comments_watchlist_id"),
        "watchlist_comments",
        ["watchlist_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_watchlist_comments_user_id"),
        "watchlist_comments",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_watchlist_comments_user_id"), table_name="watchlist_comments")
    op.drop_index(op.f("ix_watchlist_comments_watchlist_id"), table_name="watchlist_comments")
    op.drop_table("watchlist_comments")
