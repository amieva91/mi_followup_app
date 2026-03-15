"""set_administrador_email_followup_fit

Revision ID: 7a6d787c3ac4
Revises: db1dd1f49151
Create Date: 2026-03-15 22:54:39.418438

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a6d787c3ac4'
down_revision = 'db1dd1f49151'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE users SET email = 'followup.fit@gmail.com' WHERE username = 'administrador'"
    )


def downgrade():
    op.execute(
        "UPDATE users SET email = 'administrador@localhost' WHERE username = 'administrador'"
    )
