"""add_api_call_log_table

Revision ID: 8023fcfde247
Revises: a1b2c3d4e5f7
Create Date: 2026-03-15 22:41:36.160040

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8023fcfde247'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_call_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_name', sa.String(50), nullable=False),
        sa.Column('endpoint_or_operation', sa.String(255), nullable=True),
        sa.Column('called_at', sa.DateTime(), nullable=False),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('value_reported', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_call_log_api_name'), 'api_call_log', ['api_name'], unique=False)
    op.create_index(op.f('ix_api_call_log_called_at'), 'api_call_log', ['called_at'], unique=False)
    op.create_index(op.f('ix_api_call_log_user_id'), 'api_call_log', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_api_call_log_user_id'), table_name='api_call_log')
    op.drop_index(op.f('ix_api_call_log_called_at'), table_name='api_call_log')
    op.drop_index(op.f('ix_api_call_log_api_name'), table_name='api_call_log')
    op.drop_table('api_call_log')
