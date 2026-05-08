"""
Worker DB-backed para ejecutar jobs largos de `company_reports` de forma durable (sin hilos daemon de Gunicorn).

- FIFO por `COALESCE(report_enqueued_at, created_at)`
- Concurrency=1 (un proceso systemd)
- Cubre Deep Research (watchlist/full) y todo-en-uno (`full_deliver`).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

JOB_KIND_DR_WATCHLIST_MIN = "dr_watchlist_min"
JOB_KIND_DR_FULL = "dr_full"
JOB_KIND_FULL_DELIVER = "full_deliver"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _p95_seconds() -> int:
    raw = os.environ.get("FOLLOWUP_DR_P95_SECONDS", "").strip()
    if not raw:
        return 30 * 60
    try:
        return max(60, int(raw))
    except ValueError:
        return 30 * 60


def _timeout_seconds() -> int:
    return int(_p95_seconds() * 1.5)


def _sleep_seconds_idle() -> float:
    raw = os.environ.get("FOLLOWUP_JOBS_WORKER_IDLE_SLEEP_SECONDS", "").strip()
    if not raw:
        return 1.0
    try:
        return max(0.2, float(raw))
    except ValueError:
        return 1.0


def _sleep_seconds_between_jobs() -> float:
    """
    Pausa artificial tras completar un job (éxito o fallo) para limitar ritmo/coste.
    Override: FOLLOWUP_JOBS_WORKER_DELAY_BETWEEN_JOBS_SECONDS (por defecto 0).
    """
    raw = os.environ.get("FOLLOWUP_JOBS_WORKER_DELAY_BETWEEN_JOBS_SECONDS", "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def _job_kind_params() -> dict:
    return {
        "k_dr1": JOB_KIND_DR_WATCHLIST_MIN,
        "k_dr2": JOB_KIND_DR_FULL,
        "k_fd": JOB_KIND_FULL_DELIVER,
    }


def _reconcile_company_report_job_rows(engine) -> None:
    """
    Normaliza estados inconsistentes tras reinicios/deploys.
    """
    now = _utcnow()
    jp = _job_kind_params()
    with engine.connect() as conn:
        # Audio resumen (TTS) deshabilitado: cancelar cualquier job tts_only que quedara en BD.
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='cancelled',
                    job_phase='cancelled',
                    job_finished_at=COALESCE(job_finished_at, :now),
                    audio_status=CASE
                      WHEN COALESCE(audio_status,'') IN ('queued','processing') THEN 'failed'
                      ELSE audio_status END,
                    audio_error_msg=CASE
                      WHEN COALESCE(audio_status,'') IN ('queued','processing') THEN 'Audio resumen deshabilitado temporalmente.'
                      ELSE audio_error_msg END,
                    audio_progress_json=NULL
                WHERE COALESCE(job_kind,'') = 'tts_only'
                  AND COALESCE(job_status,'') IN ('queued','running')
                """
            ),
            {"now": now},
        )
        # DR: completed pero job_status sigue running
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='completed',
                    job_phase='completed',
                    job_finished_at=COALESCE(job_finished_at, completed_at, :now)
                WHERE COALESCE(job_kind, '') IN (:k_dr1, :k_dr2)
                  AND status='completed'
                  AND job_status='running'
                """
            ),
            {**jp, "now": now},
        )
        # full_deliver: DR+tail terminado y fila sigue running
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='completed',
                    job_phase=CASE
                      WHEN delivery_phase_status IS NULL THEN COALESCE(job_phase,'completed')
                      WHEN trim(CAST(delivery_phase_status AS text)) = 'completed' THEN 'completed'
                      WHEN delivery_phase_status IN ('partial','failed') THEN delivery_phase_status
                      ELSE COALESCE(job_phase,'completed') END,
                    job_finished_at=COALESCE(job_finished_at, completed_at, :now)
                WHERE job_kind = :k_fd
                  AND status='completed'
                  AND job_status='running'
                  AND COALESCE(delivery_phase_status,'') IN ('completed','partial','failed')
                """
            ),
            {**jp, "now": now},
        )
        # DR: failed pero job_status sigue running
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='failed',
                    job_phase=COALESCE(job_phase, 'failed'),
                    job_finished_at=COALESCE(job_finished_at, completed_at, :now)
                WHERE COALESCE(job_kind, '') IN (:k_dr1, :k_dr2)
                  AND status='failed'
                  AND job_status='running'
                """
            ),
            {**jp, "now": now},
        )
        # full_deliver failed (DR o informe)
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='failed',
                    job_phase='failed',
                    job_finished_at=COALESCE(job_finished_at, completed_at, :now)
                WHERE job_kind = :k_fd
                  AND status='failed'
                  AND job_status='running'
                """
            ),
            {**jp, "now": now},
        )
        # Pending marcado como running: devolver a cola
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='queued',
                    job_phase='waiting_turn',
                    job_started_at=NULL,
                    job_finished_at=NULL
                WHERE COALESCE(job_kind, '') IN (:k_dr1, :k_dr2, :k_fd)
                  AND status='pending'
                  AND job_status='running'
                """
            ),
            jp,
        )
        # Processing pero job_status está queued: marcar running (filas antiguas)
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='running',
                    job_phase=COALESCE(job_phase, 'polling_provider'),
                    job_started_at=COALESCE(job_started_at, report_enqueued_at, created_at, :now)
                WHERE COALESCE(job_kind, '') IN (:k_dr1, :k_dr2, :k_fd)
                  AND status='processing'
                  AND COALESCE(job_status, 'queued')='queued'
                """
            ),
            {**jp, "now": now},
        )
        # En cola con status processing (UI legacy): volver a pending
        conn.execute(
            text(
                """
                UPDATE company_reports
                SET status='pending'
                WHERE COALESCE(job_kind, '') IN (:k_dr1, :k_dr2, :k_fd)
                  AND job_status='queued'
                  AND status='processing'
                """
            ),
            jp,
        )
        conn.commit()


def _count_running_tracked_jobs(conn) -> int:
    n = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM company_reports
            WHERE job_status = 'running'
              AND COALESCE(job_kind, '') IN (:k_dr1, :k_dr2, :k_fd)
            """
        ),
        _job_kind_params(),
    ).scalar()
    try:
        return int(n or 0)
    except Exception:
        return 0


def _claim_next_company_report_job(engine) -> Optional[int]:
    """
    Reclama el siguiente job encolado (DR o full_deliver). Devuelve id o None.
    """
    jp = _job_kind_params()
    with engine.connect() as conn:
        if _count_running_tracked_jobs(conn) > 0:
            return None

        row = conn.execute(
            text(
                """
                SELECT id
                FROM company_reports
                WHERE COALESCE(job_status, 'queued') = 'queued'
                  AND (
                    (
                      COALESCE(job_kind, '') IN (:k_dr1, :k_dr2)
                      AND COALESCE(status, 'pending') = 'pending'
                    )
                    OR (
                      job_kind = :k_fd
                      AND COALESCE(status, 'pending') = 'pending'
                    )
                  )
                ORDER BY COALESCE(report_enqueued_at, created_at) ASC, id ASC
                LIMIT 1
                """
            ),
            jp,
        ).fetchone()
        if not row:
            return None
        rid = int(row[0])
        now = _utcnow()
        res = conn.execute(
            text(
                """
                UPDATE company_reports
                SET job_status='running',
                    job_started_at=COALESCE(job_started_at, :now),
                    job_phase='waiting_turn',
                    provider_poll_count=COALESCE(provider_poll_count, 0),
                    provider_create_attempt=COALESCE(provider_create_attempt, 0)
                WHERE id=:rid AND COALESCE(job_status, 'queued')='queued'
                """
            ),
            {"rid": rid, "now": now},
        )
        conn.commit()
        if int(getattr(res, "rowcount", 0) or 0) == 0:
            return None
        return rid


def _load_job_context(engine, report_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT r.id, r.user_id, r.asset_id, r.template_id, r.template_title, r.job_kind,
                       t.description, t.points,
                       a.name, a.symbol, a.isin
                FROM company_reports r
                LEFT JOIN report_templates t ON t.id = r.template_id
                LEFT JOIN assets a ON a.id = r.asset_id
                WHERE r.id = :rid
                """
            ),
            {"rid": int(report_id)},
        ).mappings().first()
    return dict(row) if row else {}


def _update(engine, report_id: int, **fields) -> None:
    if not fields:
        return
    cols = []
    params = {"rid": int(report_id)}
    for k, v in fields.items():
        cols.append(f"{k} = :{k}")
        params[k] = v
    sql = "UPDATE company_reports SET " + ", ".join(cols) + " WHERE id = :rid"
    with engine.connect() as conn:
        conn.execute(text(sql), params)
        conn.commit()


def _mark_failed(engine, report_id: int, msg: str, *, kind: str = "unknown") -> None:
    now = _utcnow()
    _update(
        engine,
        report_id,
        status="failed",
        error_msg=(msg or "Error")[:8000],
        completed_at=now,
        job_status="failed",
        job_finished_at=now,
        job_phase="failed",
        provider_last_error_kind=(kind or "unknown")[:40],
        provider_last_error_msg=(msg or "Error")[:8000],
    )


def _mark_completed(engine, report_id: int, content: str) -> None:
    now = _utcnow()
    _update(
        engine,
        report_id,
        status="completed",
        content=(content or ""),
        error_msg=None,
        completed_at=now,
        job_status="completed",
        job_finished_at=now,
        job_phase="completed",
    )


def _set_processing(engine, report_id: int) -> None:
    _update(engine, report_id, status="processing")


def run_once(app) -> bool:
    """
    Ejecuta un job si existe. Devuelve True si ejecutó algo.
    """
    from app import db
    from app.background_tasks_lock import background_tasks_lock
    from app.services.company_report_telemetry import sync_full_deliver_job_terminal
    from app.services.full_deliver_continuation import continue_full_deliver_after_dr
    from app.services.gemini_service import (
        GeminiServiceError,
        resume_company_report_from_interaction_id,
        run_deep_research_report,
    )
    from app.services.watchlist_ia_template import get_watchlist_ia_deep_brief, WATCHLIST_IA_REPORT_TITLE_DR_ROW

    engine = db.engine
    jp = _job_kind_params()

    # Reanudar job `running` tras reinicio del worker antes de reclamar uno nuevo.
    with engine.connect() as conn:
        rr = conn.execute(
            text(
                """
                SELECT id, COALESCE(job_kind,'') AS jk, COALESCE(gemini_interaction_id,'') AS iid
                FROM company_reports
                WHERE job_status = 'running'
                  AND COALESCE(job_kind, '') IN (:k_dr1, :k_dr2, :k_fd)
                ORDER BY COALESCE(job_started_at, report_enqueued_at, created_at) ASC, id ASC
                LIMIT 1
                """
            ),
            jp,
        ).fetchone()
    if rr:
        rid_running = int(rr[0])
        kind_running = (rr[1] or "").strip()
        iid_running = (rr[2] or "").strip()

        if kind_running == JOB_KIND_FULL_DELIVER and not iid_running:
            from app.services.full_deliver_continuation import _fail_full_deliver_report

            _fail_full_deliver_report(
                engine,
                rid_running,
                "Generación interrumpida antes de obtener respuesta de Gemini (sin interaction_id). Genera el informe de nuevo.",
            )
            return True

        if kind_running in (JOB_KIND_DR_WATCHLIST_MIN, JOB_KIND_DR_FULL) and not iid_running:
            _mark_failed(
                engine,
                rid_running,
                "Generación interrumpida antes de obtener respuesta de Gemini (sin interaction_id). Genera el informe de nuevo.",
                kind="orphan_no_iid",
            )
            return True

        # DR o full_deliver con interaction_id: reanudar polling Gemini bajo lock global.
        with app.app_context(), background_tasks_lock(app, fair_report_id=rid_running):
            try:
                _update(engine, rid_running, job_phase="polling_provider")
                resume_company_report_from_interaction_id(rid_running)
            except Exception as e:
                if kind_running == JOB_KIND_FULL_DELIVER:
                    from app.services.full_deliver_continuation import _fail_full_deliver_report

                    _fail_full_deliver_report(engine, rid_running, str(e))
                else:
                    _mark_failed(engine, rid_running, str(e), kind="provider")
                return True

            with engine.connect() as conn:
                row2 = conn.execute(
                    text(
                        """
                        SELECT status, job_kind, delivery_mode, delivery_phase_status
                        FROM company_reports WHERE id=:rid
                        """
                    ),
                    {"rid": rid_running},
                ).mappings().first()
            if not row2:
                return True
            st = row2.get("status")
            jk = (row2.get("job_kind") or "").strip()
            dm = row2.get("delivery_mode")
            dps = row2.get("delivery_phase_status")

            if st == "failed":
                sync_full_deliver_job_terminal(engine, rid_running)
            elif st == "completed":
                is_fd = dm == "full_deliver" or jk == JOB_KIND_FULL_DELIVER
                if is_fd and str(dps or "").strip() not in ("completed", "failed", "partial"):
                    continue_full_deliver_after_dr(
                        app, rid_running, skip_background_lock=True
                    )
                sync_full_deliver_job_terminal(engine, rid_running)
                if not is_fd and jk == JOB_KIND_DR_WATCHLIST_MIN:
                    try:
                        from app.services.watchlist_report_extract_service import (
                            apply_extracted_watchlist_fields,
                            extract_watchlist_fields_from_report_md,
                        )

                        ctx2 = _load_job_context(engine, rid_running)
                        with engine.connect() as conn:
                            content = conn.execute(
                                text("SELECT content FROM company_reports WHERE id=:rid"),
                                {"rid": rid_running},
                            ).scalar()
                        extracted = extract_watchlist_fields_from_report_md(content or "")
                        apply_extracted_watchlist_fields(
                            int(ctx2.get("user_id") or 0),
                            int(ctx2.get("asset_id") or 0),
                            extracted,
                        )
                    except Exception:
                        logger.exception("watchlist extract/apply failed report_id=%s", rid_running)
                elif not is_fd:
                    _update(
                        engine,
                        rid_running,
                        job_status="completed",
                        job_phase="completed",
                        job_finished_at=_utcnow(),
                    )
            return True

    rid = _claim_next_company_report_job(engine)
    if rid is None:
        return False

    ctx = _load_job_context(engine, rid)
    if not ctx:
        _mark_failed(engine, rid, "Job no encontrado", kind="internal")
        return True

    job_kind = (ctx.get("job_kind") or "").strip()

    if job_kind == JOB_KIND_FULL_DELIVER:
        from app.services.company_report_full_deliver_runner import execute_full_deliver_job
        from app.services.gemini_service import new_full_pipeline_progress_state

        with app.app_context(), background_tasks_lock(app, fair_report_id=int(rid)):
            _set_processing(engine, rid)
            p0 = new_full_pipeline_progress_state()
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE company_reports SET audio_progress_json = :j, audio_error_msg = NULL WHERE id = :rid"
                    ),
                    {"j": json.dumps(p0, ensure_ascii=False), "rid": int(rid)},
                )
                conn.commit()
            ok, _err = execute_full_deliver_job(app, engine, rid, ctx)
            sync_full_deliver_job_terminal(engine, rid)
        return True

    # Deep Research (watchlist / full) — todo bajo lock global.
    template_title = (ctx.get("template_title") or "").strip()
    if job_kind == JOB_KIND_DR_WATCHLIST_MIN:
        use_dr_row_title = template_title == WATCHLIST_IA_REPORT_TITLE_DR_ROW
        desc, points, _ = get_watchlist_ia_deep_brief(use_dr_row_title=use_dr_row_title)
        description = desc
        points_list = points
        research_prompt_style = "watchlist_minimal"
    else:
        description = (ctx.get("description") or "").strip()
        points_raw = ctx.get("points")
        points_list = []
        if points_raw:
            try:
                points_list = json.loads(points_raw) if isinstance(points_raw, str) else []
            except Exception:
                points_list = []
        research_prompt_style = "full"

    aname = (ctx.get("name") or "Desconocida").strip()
    asym = (ctx.get("symbol") or "").strip()
    aisn = (ctx.get("isin") or "").strip()

    def on_interaction_created(iid: str) -> None:
        from app.services.company_report_telemetry import persist_interaction_created

        persist_interaction_created(engine, rid, iid)

    def on_status_update(st: str, msg: str) -> None:
        from app.services.company_report_telemetry import persist_provider_poll

        persist_provider_poll(engine, rid, st or "", msg or "", bump_poll=True)

    with app.app_context(), background_tasks_lock(app, fair_report_id=int(rid)):
        _set_processing(engine, rid)
        try:
            _update(engine, rid, job_phase="creating_interaction")
            status, content = run_deep_research_report(
                aname,
                asym,
                aisn,
                description,
                points_list,
                on_status_update=on_status_update,
                on_interaction_created=on_interaction_created,
                research_prompt_style=research_prompt_style,  # type: ignore[arg-type]
            )
            if status == "completed":
                _mark_completed(engine, rid, content)
                if job_kind == JOB_KIND_DR_WATCHLIST_MIN:
                    try:
                        from app.services.watchlist_report_extract_service import (
                            apply_extracted_watchlist_fields,
                            extract_watchlist_fields_from_report_md,
                        )

                        extracted = extract_watchlist_fields_from_report_md(content or "")
                        apply_extracted_watchlist_fields(
                            int(ctx.get("user_id") or 0), int(ctx.get("asset_id") or 0), extracted
                        )
                    except Exception:
                        logger.exception("watchlist extract/apply failed report_id=%s", rid)
                return True
            if status == "timeout":
                _mark_failed(engine, rid, str(content), kind="timeout")
                return True
            _mark_failed(engine, rid, str(content), kind="provider")
            return True
        except GeminiServiceError as e:
            _mark_failed(engine, rid, str(e), kind="provider")
            return True
        except Exception as e:
            logger.exception("company_report_jobs_worker: excepción report_id=%s", rid)
            _mark_failed(engine, rid, str(e), kind="internal")
            return True


def run_forever(app) -> None:
    idle = _sleep_seconds_idle()
    delay = _sleep_seconds_between_jobs()
    logger.info(
        "company_report_jobs_worker: start (p95=%ss timeout=%ss idle_sleep=%ss delay_between_jobs=%ss)",
        _p95_seconds(),
        _timeout_seconds(),
        idle,
        delay,
    )
    with app.app_context():
        try:
            from app import db

            _reconcile_company_report_job_rows(db.engine)
        except Exception:
            logger.exception("company_report_jobs_worker: reconcile error")
        while True:
            try:
                try:
                    from app import db

                    _reconcile_company_report_job_rows(db.engine)
                except Exception:
                    pass
                did = run_once(app)
                if not did:
                    time.sleep(idle)
                elif delay and delay > 0:
                    time.sleep(delay)
            except KeyboardInterrupt:
                raise
            except Exception:
                logger.exception("company_report_jobs_worker: loop error")
                time.sleep(2.0)
