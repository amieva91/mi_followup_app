"""add spending plan tables

Revision ID: k1l2m3n4o5p6
Revises: j5f6g7h8k9l0
Create Date: 2026-04-17

"""
from alembic import op
import sqlalchemy as sa


revision = "k1l2m3n4o5p6"
down_revision = "j5f6g7h8k9l0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "spending_plan_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("max_dsr_percent", sa.Float(), nullable=False, server_default="35"),
        sa.Column("horizon_months", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "spending_plan_fixed_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expense_category_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["expense_category_id"], ["expense_categories.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "expense_category_id", name="uq_sp_fixed_cat_user_cat"),
    )
    op.create_table(
        "spending_plan_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("goal_type", sa.String(length=32), nullable=False, server_default="generic"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("amount_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("spending_plan_goals")
    op.drop_table("spending_plan_fixed_categories")
    op.drop_table("spending_plan_settings")
