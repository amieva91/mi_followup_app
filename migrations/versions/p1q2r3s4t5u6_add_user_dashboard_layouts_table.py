"""add user_dashboard_layouts table

Revision ID: p1q2r3s4t5u6
Revises: n3o4p5q6r7s8
Create Date: 2026-04-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p1q2r3s4t5u6"
down_revision = "n3o4p5q6r7s8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_dashboard_layouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.String(length=80), nullable=False),
        sa.Column("lane", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "card_id", name="uq_user_dashboard_layout_user_card"),
    )
    op.create_index(
        op.f("ix_user_dashboard_layouts_user_id"),
        "user_dashboard_layouts",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_user_dashboard_layouts_user_id"), table_name="user_dashboard_layouts")
    op.drop_table("user_dashboard_layouts")

