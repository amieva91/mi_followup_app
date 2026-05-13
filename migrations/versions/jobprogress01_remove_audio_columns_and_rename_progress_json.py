"""remove audio columns; rename progress json

Revision ID: jobprogress01
Revises: audioattempt01
Create Date: 2026-05-08

Objetivo:
- Eliminar definitivamente el soporte de audio/TTS en `company_reports` (columnas `audio_*`).
- Renombrar `audio_progress_json` (que ya se usa como progreso general de jobs/pipelines)
  a un nombre neutro: `job_progress_json`.

Nota SQLite:
Usamos `batch_alter_table` para compatibilidad y para permitir drop de columnas en SQLite.
"""

from alembic import op
import sqlalchemy as sa


revision = "jobprogress01"
down_revision = "audioattempt01"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Añadir nuevo nombre de progreso.
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("job_progress_json", sa.Text(), nullable=True))

    # 2) Copiar datos legacy.
    op.execute(
        """
        UPDATE company_reports
        SET job_progress_json = audio_progress_json
        WHERE job_progress_json IS NULL AND audio_progress_json IS NOT NULL
        """
    )

    # 3) Eliminar columnas de audio y el nombre legacy de progreso.
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.drop_column("audio_progress_json")
        batch_op.drop_column("audio_generation_attempt")
        batch_op.drop_column("audio_completed_at")
        batch_op.drop_column("audio_error_msg")
        batch_op.drop_column("audio_status")
        batch_op.drop_column("audio_path")
        batch_op.drop_column("audio_enqueued_at")


def downgrade():
    # Downgrade best-effort: reintroduce columnas de audio y restaurar nombre legacy.
    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("audio_enqueued_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("audio_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("audio_status", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("audio_error_msg", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("audio_completed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("audio_generation_attempt", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("audio_progress_json", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE company_reports
        SET audio_progress_json = job_progress_json
        WHERE audio_progress_json IS NULL AND job_progress_json IS NOT NULL
        """
    )

    with op.batch_alter_table("company_reports", schema=None) as batch_op:
        batch_op.drop_column("job_progress_json")
