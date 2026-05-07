"""
Generación de audio TTS (solo) vía cola del worker (``job_kind='tts_only'``).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


def execute_tts_only_job(app: Any, engine: Any, report_id: int) -> None:
    """Genera WAV; actualiza audio_* y termina job telemetry. Caller tiene lock global."""
    from app.services.gemini_service import generate_report_tts_audio

    rid = int(report_id)

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT content FROM company_reports WHERE id = :rid"),
            {"rid": rid},
        ).fetchone()
    if not row:
        return
    report_content = row[0] or ""

    output_folder = app.config.get("OUTPUT_FOLDER") or (
        Path(__file__).resolve().parent.parent.parent / "output"
    )
    audio_dir = Path(output_folder).resolve() / "reports_audio"
    audio_path = audio_dir / f"report_{rid}.wav"
    now_str = datetime.utcnow().isoformat()
    final_rel = f"reports_audio/report_{rid}.wav"

    def _persist_audio_progress(pj: dict) -> None:
        import json

        c = engine.connect()
        try:
            c.execute(
                text("UPDATE company_reports SET audio_progress_json = :j WHERE id = :rid"),
                {"j": json.dumps(pj, ensure_ascii=False), "rid": rid},
            )
            c.commit()
        except Exception:
            c.rollback()
        finally:
            c.close()

    try:
        generate_report_tts_audio(report_content, str(audio_path), on_progress=_persist_audio_progress)
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET audio_status = 'completed', audio_error_msg = NULL,
                        audio_path = :path,
                        audio_completed_at = :now,
                        audio_progress_json = NULL,
                        job_status = 'completed', job_phase = 'completed',
                        job_finished_at = :now
                    WHERE id = :rid
                    """
                ),
                {"path": final_rel, "now": now_str, "rid": rid},
            )
            conn.commit()
    except Exception as e:
        logger.exception("tts_only job report_id=%s", rid)
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET audio_status = 'failed', audio_error_msg = :err,
                          audio_path = NULL,
                          job_status = 'failed', job_phase = 'failed',
                          job_finished_at = :now
                    WHERE id = :rid
                    """
                ),
                {"err": str(e)[:8000], "now": now_str, "rid": rid},
            )
            conn.commit()
