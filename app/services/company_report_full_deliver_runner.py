"""
Ejecución del pipeline «informe + audio + correo» (full_deliver) sin hilos daemon.

Caller debe tener ``app.app_context()`` y **debe tener adquirido**
``background_tasks_lock(app, fair_report_id=...)`` antes de llamar aquí para cola global FIFO.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


def execute_full_deliver_job(app: Any, engine: Any, report_id: int, ctx: dict) -> tuple[bool, str | None]:
    """
    Ejecuta DR + tail (resumen Flash, TTS, correo).

    Devuelve (ok, error_msg).
    Assume la fila ya está ``status='processing'`` (y lock global activo si aplica).
    """
    from app.services.gemini_service import GeminiServiceError, new_full_pipeline_progress_state, run_deep_research_report
    from app.services.full_deliver_continuation import _fail_full_deliver_report, execute_full_deliver_tail

    rid = int(report_id)
    user_id = int(ctx["user_id"])
    asset_id = int(ctx["asset_id"])
    description = (ctx.get("description") or "").strip()
    points_raw = ctx.get("points")
    points_list: list = []
    if points_raw:
        try:
            points_list = json.loads(points_raw) if isinstance(points_raw, str) else []
        except Exception:
            points_list = []
    aname = (ctx.get("name") or "Desconocida") or "Desconocida"
    asym = (ctx.get("symbol") or "").strip()
    aisn = (ctx.get("isin") or "").strip()
    report_template_title = (ctx.get("template_title") or f"Informe {rid}")[:200]

    pstate: dict = new_full_pipeline_progress_state()

    def _persist(obj: dict) -> None:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE company_reports SET audio_progress_json = :j, audio_error_msg = NULL WHERE id = :rid"
                ),
                {"j": json.dumps(obj, ensure_ascii=False), "rid": rid},
            )
            conn.commit()

    def _infer_dr_job_phase(api_status: str, message: str) -> str | None:
        msg = (message or "").lower()
        if "creando deep research" in msg or "(modo directo)" in msg:
            return "creating_interaction"
        if api_status == "completed":
            return None
        if "estado:" in msg and "interaction" in msg:
            return "polling_provider"
        if "interaction_id=" in msg or " último_estado=" in msg:
            return "polling_provider"
        return None

    def _on_dr_status(st: str, msg: str) -> None:
        from app.services.company_report_telemetry import persist_provider_poll

        jp = _infer_dr_job_phase(st or "", msg or "")
        persist_provider_poll(engine, rid, st or "", msg, job_phase=jp, bump_poll=True)

    def _save_iid(iid: str) -> None:
        from app.services.company_report_telemetry import persist_interaction_created

        persist_interaction_created(engine, rid, iid)

    def _on_report_subs(subs: list) -> None:
        nonlocal pstate
        for i in range(min(len(subs), len(pstate["steps"]))):
            pstate["steps"][i] = dict(subs[i])
        _persist(pstate)

    try:
        _persist(pstate)
        app.logger.info(
            "full_deliver job: DR inicio report_id=%s asset_id=%s user_id=%s",
            rid,
            asset_id,
            user_id,
        )
        st_dr, content_dr = run_deep_research_report(
            aname,
            asym,
            aisn,
            description,
            points_list,
            on_interaction_created=_save_iid,
            on_report_substeps=_on_report_subs,
            on_status_update=_on_dr_status,
        )
    except GeminiServiceError as e:
        _fail_full_deliver_report(engine, rid, str(e))
        return False, str(e)
    except Exception as e:
        logger.exception("full_deliver job DR report_id=%s", rid)
        _fail_full_deliver_report(engine, rid, str(e)[:8000])
        return False, str(e)

    if st_dr != "completed":
        _fail_full_deliver_report(engine, rid, (content_dr or "")[:8000])
        return False, (content_dr or "")[:8000]

    try:
        execute_full_deliver_tail(
            app,
            engine=engine,
            report_id=rid,
            user_id=user_id,
            asset_id=asset_id,
            aname=aname,
            report_template_title=report_template_title,
            content_dr=content_dr or "",
            pstate=pstate,
        )
    except Exception as e:
        logger.exception("full_deliver job tail report_id=%s", rid)
        return False, str(e)[:8000]

    from app.services.company_report_telemetry import sync_full_deliver_job_terminal

    sync_full_deliver_job_terminal(engine, rid)

    return True, None
