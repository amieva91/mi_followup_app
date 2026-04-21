"""compat: keep alembic revision q7r8s9t0u1v2

Revision ID: q7r8s9t0u1v2
Revises: p1q2r3s4t5u6
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "q7r8s9t0u1v2"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade():
    # Compatibilidad de historial: esta revisión pudo existir en despliegues
    # previos. Se mantiene como no-op para evitar desalineación de alembic.
    pass


def downgrade():
    pass

