"""
Cola de entrega del flujo «todo en uno» (resumen Flash → TTS → correo) tras Deep Research.

Se reutiliza desde ``generate-deliver`` y desde la reanudación tras reinicio de workers,
cuando Deep Research ya quedó persistido pero la cola larga se interrumpió.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask
from sqlalchemy import bindparam, text

from app import db
from app.background_tasks_lock import background_tasks_lock
from app.models.company_report import CompanyReport
from app.models.user import User

logger = logging.getLogger(__name__)


def _legacy_incomplete_full_deliver_tail(report: CompanyReport) -> bool:
    """Heurística para informes antiguos sin ``delivery_mode`` pero con cola de entrega a medias."""
    if (report.status or "") != "completed" or not (report.content or "").strip():
        return False
    sm = (report.summary_content or "").strip()
    au = getattr(report, "audio_status", None)
    em = getattr(report, "email_status", None)
    if sm and au == "completed" and em == "completed":
        return False
    raw = str(getattr(report, "audio_progress_json", None) or "")
    if '"full_pipeline"' in raw or "'full_pipeline'" in raw:
        return True
    if em is not None:
        return True
    if au in ("processing", "completed", "failed", "queued"):
        return True
    return False


def _full_deliver_tail_timeout_seconds() -> int:
    import os

    try:
        return max(300, int(str(os.environ.get("FULL_DELIVER_TAIL_TIMEOUT_SECONDS", "3600")).strip()))
    except ValueError:
        return 3600


def schedule_full_delivery_continuation(app: Flask, report_id: int) -> None:
    """Lanza continuación en un hilo daemon (misma estrategia que otros runners)."""
    import threading

    def _run() -> None:
        try:
            with app.app_context():
                continue_full_deliver_after_dr(app, report_id)
        except Exception:
            logger.exception("schedule_full_delivery_continuation: report_id=%s", report_id)

    threading.Thread(target=_run, daemon=True).start()


def continue_full_deliver_after_dr(app: Flask, report_id: int) -> None:
    """
    Ejecuta la cola de entrega bajo ``background_tasks_lock``.
    Idempotente: si ya hay resumen/audio/correo completos, sale sin duplicar trabajo.
    """
    with background_tasks_lock(app):
        report = CompanyReport.query.filter_by(id=report_id).first()
        if not report:
            return
        dm = getattr(report, "delivery_mode", None)
        ph = getattr(report, "delivery_phase_status", None)
        if dm != "full_deliver":
            if not _legacy_incomplete_full_deliver_tail(report):
                return
        elif ph in ("completed", "failed", "partial"):
            return
        content_dr = (report.content or "").strip()
        if not content_dr:
            logger.warning("continue_full_deliver: sin content report_id=%s", report_id)
            return

        user_id = int(report.user_id)
        asset_id = int(report.asset_id)
        report_template_title = (report.template_title or f"Informe {report_id}")[:200]

        engine = db.engine
        aname = "Desconocida"
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT name, symbol, isin FROM assets WHERE id = :aid"),
                    {"aid": asset_id},
                ).fetchone()
            if row:
                aname = row[0] or "Desconocida"
        except Exception:
            pass

        pstate = None
        raw = getattr(report, "audio_progress_json", None)
        if raw:
            try:
                obj = json.loads(str(raw))
                if isinstance(obj, dict) and obj.get("full_pipeline"):
                    pstate = obj
            except Exception:
                pstate = None

        execute_full_deliver_tail(
            app,
            engine=engine,
            report_id=report_id,
            user_id=user_id,
            asset_id=asset_id,
            aname=aname,
            report_template_title=report_template_title,
            content_dr=report.content or "",
            pstate=pstate,
        )


def execute_full_deliver_tail(
    app: Flask,
    *,
    engine: Any,
    report_id: int,
    user_id: int,
    asset_id: int,
    aname: str,
    report_template_title: str,
    content_dr: str,
    pstate: dict | None,
) -> None:
    """Resumen + TTS + correo. Actualiza ``delivery_phase_status`` y pasos en JSON."""
    from app.services.gemini_service import (
        _get_auto_collab_loop,
        fallback_report_summary_markdown,
        generate_report_email_summary,
        generate_report_tts_audio,
        merge_full_pipeline_with_tts_progress,
        new_full_pipeline_progress_state,
        report_substeps_after_dr_ok,
    )
    from app.utils.email import send_report_email

    log = app.logger

    def _persist(obj: dict) -> None:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE company_reports SET audio_progress_json = :j, audio_error_msg = NULL WHERE id = :rid"
                ),
                {"j": json.dumps(obj, ensure_ascii=False), "rid": report_id},
            )
            conn.commit()

    if pstate is None:
        pstate = new_full_pipeline_progress_state()
        single_shot = not _get_auto_collab_loop()
        subs_ok = report_substeps_after_dr_ok(single_shot, "ok")
        for i in range(min(len(subs_ok), len(pstate["steps"]))):
            pstate["steps"][i] = subs_ok[i]
        _persist(pstate)

    single_shot = not _get_auto_collab_loop()

    def _reload_report() -> CompanyReport | None:
        db.session.expire_all()
        return CompanyReport.query.filter_by(id=report_id).first()

    report = _reload_report()
    if not report:
        return

    summary_md_pl = (report.summary_content or "").strip()

    if not summary_md_pl:
        subs_ld = report_substeps_after_dr_ok(single_shot, "loading")
        for i in range(min(len(subs_ld), len(pstate["steps"]))):
            pstate["steps"][i] = subs_ld[i]
        _persist(pstate)
        try:
            summary_md_pl = generate_report_email_summary(content_dr or "")
        except Exception:
            summary_md_pl = fallback_report_summary_markdown(content_dr or "")
        if not isinstance(summary_md_pl, str) or not summary_md_pl.strip():
            summary_md_pl = fallback_report_summary_markdown(content_dr or "")
        subs_ok2 = report_substeps_after_dr_ok(single_shot, "ok")
        for i in range(min(len(subs_ok2), len(pstate["steps"]))):
            pstate["steps"][i] = subs_ok2[i]
        _persist(pstate)

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET status = 'completed', content = :c, summary_content = :sm,
                    error_msg = NULL, completed_at = :now,
                    delivery_mode = 'full_deliver', delivery_phase_status = 'processing'
                WHERE id = :rid
                """
            ),
            {"c": content_dr, "sm": summary_md_pl, "now": now_str, "rid": report_id},
        )
        conn.commit()

    report = _reload_report()
    if not report:
        return

    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM company_reports WHERE user_id = :uid AND asset_id = :aid"),
            {"uid": user_id, "aid": asset_id},
        ).scalar()
        if cnt and cnt > 5:
            lim = int(cnt) - 5
            ids = [
                r[0]
                for r in conn.execute(
                    text(
                        """
                        SELECT id FROM company_reports
                        WHERE user_id = :uid AND asset_id = :aid
                        ORDER BY created_at ASC LIMIT :lim
                        """
                    ),
                    {"uid": user_id, "aid": asset_id, "lim": lim},
                ).fetchall()
            ]
            if ids:
                stmt = text("DELETE FROM company_reports WHERE id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                )
                conn.execute(stmt, {"ids": ids})
        conn.commit()

    output_folder = app.config.get("OUTPUT_FOLDER") or (
        Path(__file__).resolve().parent.parent.parent / "output"
    )
    audio_dir = Path(output_folder).resolve() / "reports_audio"
    audio_path = audio_dir / f"report_{report_id}.wav"

    au_st = getattr(report, "audio_status", None)
    if au_st != "completed":
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET audio_status = 'processing', audio_error_msg = NULL, audio_path = NULL, audio_completed_at = NULL
                    WHERE id = :rid
                    """
                ),
                {"rid": report_id},
            )
            conn.commit()

        pstate["steps"][4]["status"] = "loading"
        pstate["steps"][4]["error"] = None
        _persist(pstate)

        def on_tts(tj: dict) -> None:
            nonlocal pstate
            pstate = merge_full_pipeline_with_tts_progress(pstate, tj)
            _persist(pstate)

        try:
            generate_report_tts_audio(content_dr or "", str(audio_path), on_progress=on_tts)
        except Exception as tts_e:
            log.exception("TTS en full_deliver_tail: %s", tts_e)
            pstate["steps"][4]["status"] = "error"
            pstate["steps"][4]["error"] = str(tts_e)[:4000]
            pstate["steps"][5]["status"] = "error"
            pstate["steps"][5]["error"] = str(tts_e)[:4000]
            _persist(pstate)
            with engine.connect() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE company_reports
                        SET audio_status = 'failed', audio_error_msg = :e,
                            delivery_phase_status = 'failed'
                        WHERE id = :rid
                        """
                    ),
                    {"e": str(tts_e)[:8000], "rid": report_id},
                )
                conn.commit()
            return

        t_ok = datetime.utcnow().isoformat()
        pstate["steps"][4]["status"] = "ok"
        pstate["steps"][4]["error"] = None
        pstate["steps"][5]["status"] = "ok"
        pstate["steps"][5]["error"] = None
        pstate["steps"][6]["status"] = "loading"
        pstate["steps"][6]["error"] = None
        _persist(pstate)

        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET audio_status = 'completed',
                        audio_path = :path,
                        audio_error_msg = NULL,
                        audio_completed_at = :ac,
                        email_status = 'processing',
                        email_error_msg = NULL,
                        email_completed_at = NULL
                    WHERE id = :rid
                    """
                ),
                {
                    "path": f"reports_audio/report_{report_id}.wav",
                    "ac": t_ok,
                    "rid": report_id,
                },
            )
            conn.commit()
    else:
        rel = (getattr(report, "audio_path", None) or "").strip()
        if rel:
            audio_path = Path(output_folder).resolve() / rel
        pstate["steps"][4]["status"] = "ok"
        pstate["steps"][5]["status"] = "ok"
        pstate["steps"][6]["status"] = "loading"
        pstate["steps"][6]["error"] = None
        _persist(pstate)

    u = User.query.get(user_id)
    if not u or not u.email:
        pstate["steps"][6]["status"] = "error"
        pstate["steps"][6]["error"] = "Usuario sin email"
        _persist(pstate)
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET audio_status = 'failed', audio_error_msg = 'Usuario sin email',
                        delivery_phase_status = 'failed'
                    WHERE id = :rid
                    """
                ),
                {"rid": report_id},
            )
            conn.commit()
        return

    try:
        send_report_email(
            user=u,
            asset_name=aname,
            report_title=report_template_title,
            email_body_markdown=summary_md_pl,
            audio_file_path=str(audio_path),
            full_report_markdown_for_pdf=content_dr or "",
        )
    except Exception as em_e:
        log.exception("Correo en full_deliver_tail: %s", em_e)
        pstate["steps"][6]["status"] = "error"
        pstate["steps"][6]["error"] = str(em_e)[:4000]
        _persist(pstate)
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET email_status = 'failed', email_error_msg = :e, email_completed_at = NULL,
                        delivery_phase_status = 'partial'
                    WHERE id = :rid
                    """
                ),
                {"e": str(em_e)[:8000], "rid": report_id},
            )
            conn.commit()
        return

    pstate["steps"][6]["status"] = "ok"
    pstate["steps"][6]["error"] = None
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET email_status = 'completed', email_error_msg = NULL, email_completed_at = :ec,
                    audio_progress_json = NULL,
                    delivery_phase_status = 'completed'
                WHERE id = :rid
                """
            ),
            {
                "ec": datetime.utcnow().isoformat(),
                "rid": report_id,
            },
        )
        conn.commit()


def _fail_full_deliver_report(engine: Any, report_id: int, err: str) -> None:
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET status = 'failed', error_msg = :e, completed_at = :now
                WHERE id = :rid
                """
            ),
            {"e": (err or "")[:8000], "now": now_str, "rid": int(report_id)},
        )
        conn.commit()


def run_full_deliver_pending_recovery(app: Flask, report_id: int) -> None:
    """
    Reclama un informe «todo en uno» dejado en ``pending`` (p. ej. worker reciclado)
    y ejecuta Deep Research + cola de entrega.
    """
    from app.services.gemini_service import GeminiServiceError, run_deep_research_report, new_full_pipeline_progress_state

    with app.app_context(), background_tasks_lock(app):
        engine = db.engine
        rid = int(report_id)
        with engine.connect() as conn:
            r = conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET status = 'processing',
                        delivery_mode = 'full_deliver',
                        delivery_phase_status = COALESCE(delivery_phase_status, 'processing')
                    WHERE id = :rid AND status = 'pending'
                      AND (
                        delivery_mode = 'full_deliver'
                        OR (
                          delivery_mode IS NULL
                          AND audio_progress_json LIKE '%full_pipeline%'
                        )
                      )
                    """
                ),
                {"rid": rid},
            )
            conn.commit()
            if getattr(r, "rowcount", 0) == 0:
                return

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT r.user_id, r.asset_id, r.template_title, t.description, t.points, a.name, a.symbol, a.isin
                    FROM company_reports r
                    LEFT JOIN report_templates t ON t.id = r.template_id
                    LEFT JOIN assets a ON a.id = r.asset_id
                    WHERE r.id = :rid
                    """
                ),
                {"rid": rid},
            ).fetchone()
        if not row:
            _fail_full_deliver_report(engine, rid, "Informe no encontrado")
            return

        user_id, asset_id, template_title, desc, points_json, aname, asym, aisn = row
        description = (desc or "").strip()
        points: list = []
        if points_json:
            try:
                points = json.loads(points_json) if isinstance(points_json, str) else []
            except Exception:
                points = []
        aname = (aname or "Desconocida") or "Desconocida"
        asym = asym or ""
        aisn = aisn or ""
        rtitle = (template_title or f"Informe {rid}")[:200]

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

        _persist(pstate)

        def _save_iid(iid: str) -> None:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE company_reports SET gemini_interaction_id = :iid "
                        "WHERE id = :rid AND status = 'processing'"
                    ),
                    {"iid": (iid or "")[:100], "rid": rid},
                )
                conn.commit()

        def _on_report_subs(subs: list) -> None:
            nonlocal pstate
            for i in range(min(len(subs), len(pstate["steps"]))):
                pstate["steps"][i] = dict(subs[i])
            _persist(pstate)

        app.logger.info(
            "full_deliver recovery: DR pendiente report_id=%s asset_id=%s user_id=%s",
            rid,
            asset_id,
            user_id,
        )

        try:
            st_dr, content_dr = run_deep_research_report(
                aname,
                asym,
                aisn,
                description,
                points,
                on_interaction_created=_save_iid,
                on_report_substeps=_on_report_subs,
            )
        except GeminiServiceError as e:
            _fail_full_deliver_report(engine, rid, str(e))
            return
        except Exception:
            logger.exception("full_deliver recovery DR report_id=%s", rid)
            _fail_full_deliver_report(engine, rid, "Error en Deep Research")
            return

        if st_dr != "completed":
            _fail_full_deliver_report(engine, rid, (content_dr or "")[:8000])
            return

        execute_full_deliver_tail(
            app,
            engine=engine,
            report_id=rid,
            user_id=int(user_id),
            asset_id=int(asset_id),
            aname=aname,
            report_template_title=rtitle,
            content_dr=content_dr or "",
            pstate=pstate,
        )


def recover_stuck_full_delivery_tails(app: Flask, app_logger=None) -> None:
    """
    Tras reinicio: re-lanza la cola de entrega para informes marcados como full_deliver
    que siguen en fase ``processing``.
    """
    log = app_logger or logger
    try:
        rows = (
            CompanyReport.query.filter(CompanyReport.delivery_mode == "full_deliver")
            .filter(
                db.or_(
                    CompanyReport.delivery_phase_status == "processing",
                    CompanyReport.delivery_phase_status.is_(None),
                )
            )
            .filter(CompanyReport.status == "completed")
            .filter(CompanyReport.content.isnot(None))
            .order_by(CompanyReport.id.asc())
            .limit(5)
            .all()
        )
        for r in rows:
            schedule_full_delivery_continuation(app, int(r.id))
        if rows:
            log.info("full_deliver: reanudación programada para %s informes", len(rows))
    except Exception:
        log.exception("recover_stuck_full_delivery_tails")


def expire_stale_full_delivery_tails(app_logger=None) -> int:
    """Marca como ``partial`` entregas que llevan demasiado en cola tras DR completado."""
    from datetime import timedelta

    log = app_logger or logger
    sec = _full_deliver_tail_timeout_seconds()
    cutoff = datetime.utcnow() - timedelta(seconds=sec)
    msg = (
        f"Tiempo máximo ({sec}s) superado en la entrega todo-en-uno (resumen/audio/correo). "
        "Revisa el informe o vuelve a lanzar la entrega."
    )
    try:
        res = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET delivery_phase_status = 'partial', error_msg = :msg
                WHERE delivery_mode = 'full_deliver'
                  AND (delivery_phase_status = 'processing' OR delivery_phase_status IS NULL)
                  AND status = 'completed'
                  AND completed_at IS NOT NULL
                  AND completed_at < :cutoff
                  AND (
                    summary_content IS NULL OR TRIM(summary_content) = ''
                    OR audio_status IS NULL OR audio_status NOT IN ('completed','failed')
                    OR email_status IS NULL OR email_status NOT IN ('completed','failed')
                  )
                """
            ),
            {"cutoff": cutoff, "msg": msg[:8000]},
        )
        n = int(getattr(res, "rowcount", 0) or 0)
        if n:
            db.session.commit()
            log.warning("full_deliver: expiradas %s entregas a medias (tail timeout %ss)", n, sec)
        else:
            db.session.rollback()
        return n
    except Exception:
        db.session.rollback()
        log.exception("expire_stale_full_delivery_tails")
        return 0
