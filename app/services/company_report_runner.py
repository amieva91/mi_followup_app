"""
Re-ejecutores (best-effort) de informes en cola.

Motivo: los informes se procesan en hilos daemon. Si un worker de Gunicorn se recicla/reinicia,
un informe puede quedarse en `pending` sin que haya ningún hilo vivo que lo consuma.

Este módulo permite "reanudar" informes `pending` lanzando un nuevo hilo que intenta
reclamar la fila con un UPDATE atómico (pending -> processing). Se ejecuta bajo
`background_tasks_lock` para respetar la cola global.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import text

logger = logging.getLogger(__name__)


def run_report_only_by_id(app, report_id: int) -> None:
    """
    (Re)ejecuta un informe "solo informe" (Deep Research + resumen Flash) si sigue en `pending`.

    No toca pipelines `full_pipeline` (todo-en-uno).
    """
    from app import db
    from app.background_tasks_lock import background_tasks_lock
    from app.services.gemini_service import (
        run_deep_research_report,
        new_report_stages_progress_state,
        generate_report_email_summary,
        fallback_report_summary_markdown,
        report_substeps_after_dr_ok,
        _get_auto_collab_loop,
        GeminiServiceError,
    )

    with app.app_context(), background_tasks_lock(app):
        engine = db.engine

        # 1) Reclamar fila: pending -> processing (si ya fue reclamada, no hacemos nada)
        with engine.connect() as conn:
            r = conn.execute(
                text(
                    "UPDATE company_reports SET status='processing' "
                    "WHERE id=:rid AND status='pending'"
                ),
                {"rid": int(report_id)},
            )
            conn.commit()
            if r.rowcount == 0:
                return

        def _update_status(st: str, *, content_val=None, error_val=None, clear_progress: bool = False) -> None:
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            with engine.connect() as conn:
                if clear_progress and st == "completed":
                    conn.execute(
                        text(
                            """
                            UPDATE company_reports
                            SET status=:st, completed_at=:now, content=:content, error_msg=:error,
                                audio_progress_json=NULL
                            WHERE id=:rid
                            """
                        ),
                        {
                            "st": st,
                            "now": now_str,
                            "content": content_val,
                            "error": error_val,
                            "rid": int(report_id),
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            UPDATE company_reports
                            SET status=:st, completed_at=:now, content=:content, error_msg=:error
                            WHERE id=:rid
                            """
                        ),
                        {
                            "st": st,
                            "now": now_str,
                            "content": content_val,
                            "error": error_val,
                            "rid": int(report_id),
                        },
                    )
                conn.commit()

        # 2) Leer contexto (asset + plantilla) desde DB
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT r.user_id, r.asset_id, r.template_id, t.description, t.points, a.name, a.symbol, a.isin
                    FROM company_reports r
                    LEFT JOIN report_templates t ON t.id = r.template_id
                    LEFT JOIN assets a ON a.id = r.asset_id
                    WHERE r.id = :rid
                    """
                ),
                {"rid": int(report_id)},
            ).fetchone()
        if not row:
            _update_status("failed", error_val="Informe no encontrado")
            return

        _user_id, asset_id, _template_id, desc, points_json, aname, asym, aisn = row
        description = (desc or "").strip()
        points = []
        if points_json:
            try:
                points = json.loads(points_json) if isinstance(points_json, str) else []
            except Exception:
                points = []

        aname = aname or "Desconocida"
        asym = asym or ""
        aisn = aisn or ""

        def _save_interaction_id(iid: str) -> None:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE company_reports SET gemini_interaction_id=:iid "
                        "WHERE id=:rid AND status='processing'"
                    ),
                    {"iid": (iid or "")[:100], "rid": int(report_id)},
                )
                conn.commit()

        def _persist_report_stages(subs: list) -> None:
            base = new_report_stages_progress_state()
            base["steps"] = subs
            with engine.connect() as conn:
                conn.execute(
                    text("UPDATE company_reports SET audio_progress_json=:j WHERE id=:rid"),
                    {"j": json.dumps(base, ensure_ascii=False), "rid": int(report_id)},
                )
                conn.commit()

        # Inicializar progreso (si faltaba)
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE company_reports SET audio_progress_json=:j WHERE id=:rid"),
                {"j": json.dumps(new_report_stages_progress_state(), ensure_ascii=False), "rid": int(report_id)},
            )
            conn.commit()

        logger.info("Deep Research runner: reanudando pending report_id=%s", report_id)

        try:
            status, content = run_deep_research_report(
                aname,
                asym,
                aisn,
                description,
                points,
                on_interaction_created=_save_interaction_id,
                on_report_substeps=_persist_report_stages,
            )
        except GeminiServiceError as e:
            _update_status("failed", error_val=str(e), clear_progress=False)
            return
        except Exception as e:
            _update_status("failed", error_val=str(e), clear_progress=False)
            return

        if status != "completed":
            _update_status("failed", error_val=str(content)[:8000], clear_progress=False)
            return

        # Generar resumen Flash (best-effort)
        try:
            single_shot = not _get_auto_collab_loop()
            _persist_report_stages(report_substeps_after_dr_ok(single_shot, "loading"))
            summary_md = generate_report_email_summary(content or "")
            _persist_report_stages(report_substeps_after_dr_ok(single_shot, "ok"))
        except Exception:
            summary_md = fallback_report_summary_markdown(content or "")

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET status='completed', completed_at=:now, content=:content, summary_content=:sm,
                        error_msg=NULL, audio_progress_json=NULL
                    WHERE id=:rid
                    """
                ),
                {"now": now_str, "content": content, "sm": summary_md, "rid": int(report_id)},
            )
            conn.commit()

        logger.info("Deep Research runner: completado report_id=%s", report_id)

