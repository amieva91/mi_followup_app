"""Fix currency BG to BGN (Bulgarian Lev)

BG is a country code (Bulgaria), not ISO 4217. Correct code is BGN.
Updates assets and transactions with currency='BG' to 'BGN'.

Revision ID: b7c8d9e0f1a2
Revises: d7e8f9a0b1c2
Create Date: 2026-03-07

"""
from alembic import op


revision = 'b7c8d9e0f1a2'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE assets SET currency = 'BGN' WHERE currency = 'BG'")
    op.execute("UPDATE transactions SET currency = 'BGN' WHERE currency = 'BG'")
    # AssetRegistry si existe
    try:
        op.execute("UPDATE asset_registry SET currency = 'BGN' WHERE currency = 'BG'")
    except Exception:
        pass


def downgrade():
    # Revertir no es trivial (podría haber BGN legítimos). Dejamos vacío.
    pass
