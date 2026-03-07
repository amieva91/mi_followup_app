"""Add real_estate_properties, property_valuations, property_id to debt_plans

Revision ID: d9e0f1a2b3c4
Revises: b7c8d9e0f1a2
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'd9e0f1a2b3c4'
down_revision = ('b7c8d9e0f1a2', 'fix_health_detail_001')
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'real_estate_properties',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('property_type', sa.String(length=20), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('purchase_price', sa.Float(), nullable=False),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'property_valuations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['property_id'], ['real_estate_properties.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('debt_plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('property_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_debt_plans_property_id',
            'real_estate_properties',
            ['property_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('debt_plans', schema=None) as batch_op:
        batch_op.drop_constraint('fk_debt_plans_property_id', type_='foreignkey')
        batch_op.drop_column('property_id')

    op.drop_table('property_valuations')
    op.drop_table('real_estate_properties')
