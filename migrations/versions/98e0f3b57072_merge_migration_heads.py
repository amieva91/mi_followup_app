"""merge migration heads

Revision ID: 98e0f3b57072
Revises: 19cce9d564ba, 4015141a3bbe
Create Date: 2025-10-06 10:03:05.416413

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98e0f3b57072'
down_revision = ('19cce9d564ba', '4015141a3bbe')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
