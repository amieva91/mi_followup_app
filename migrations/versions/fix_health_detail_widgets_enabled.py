"""fix health_detail_* widgets to enabled=True

Revision ID: fix_health_detail_001
Revises: 0154d7bbbbb1
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa


revision = 'fix_health_detail_001'
down_revision = '0154d7bbbbb1'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE user_dashboard_configs
            SET enabled = 1
            WHERE widget_id LIKE 'health_detail_%%' AND NOT enabled
        """)
    )


def downgrade():
    pass  # No revert needed
