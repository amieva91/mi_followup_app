"""add audio_generation_attempt to company_reports

Revision ID: audioattempt01
Revises: jobtelemetry01
Create Date: 2026-05-07

Cuenta encoladas de síntesis TTS (solo informe informe+t audio) hasta 3; se devuelve a 0 cuando el WAV termina bien.
"""

from alembic import op
import sqlalchemy as sa


revision = "audioattempt01"
down_revision = "jobtelemetry01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company_reports",
        sa.Column("audio_generation_attempt", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("company_reports", "audio_generation_attempt")
