"""add user_dashboard_configs table

Revision ID: 0154d7bbbbb1
Revises: c1d2e3f4a5b6
Create Date: 2026-03-01 01:20:23.250832

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0154d7bbbbb1'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_dashboard_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('widget_id', sa.String(length=50), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'widget_id', name='uq_user_widget')
    )


def downgrade():
    op.drop_table('user_dashboard_configs')
