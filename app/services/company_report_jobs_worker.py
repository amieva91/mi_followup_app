"""
Worker DB-backed para ejecutar jobs largos de `company_reports` de forma durable (sin hilos daemon de Gunicorn).

- FIFO por `report_enqueued_at` (o `created_at` fallback)
- Concurrency=1 (un proceso systemd)
- Persiste telemetría mínima en columnas de `company_reports`
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


JOB_KIND_DR_WATCHLIST_MIN = "dr_watchlist_min"
JOB_KIND_DR_FULL = "dr_full"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _p95_seconds() -> int:
    # P95 fijo inicial (30 min) configurable por env
    raw = os.environ.get("FOLLOWUP_DR_P95_SECONDS", "").strip()
    if not raw:
        return 30 * 60
    try:
        return max(60, int(raw))
    except ValueError:
        return 30 * 60


def _timeout_seconds() -> int:
    # margen +50%
    return int(_p95_seconds() * 1.5)


def _sleep_seconds_idle() -> float:
    raw = os.environ.get("FOLLOWUP_JOBS_WORKER_IDLE_SLEEP_SECONDS", "").strip()
    if not raw:
        return 1.0
    try:
        return max(0.2, float(raw))
    except ValueError:
        return 1.0


def _claim_next_company_report_job(engine) -> Optional[int]:
    """
    Reclama el siguiente `company_reports` encolado para DR.
    Devuelve report_id o None si no hay.
    """
    # Concurrency=1 global: si hay un DR marcado como running, no reclamar otro.
    with engine.connect() as conn:
        n_running = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM company_reports
                WHERE job_status = 'running'
                  AND COALESCE(job_kind, '') IN (:k1, :k2)
                  AND COALESCE(status, '') IN ('processing', 'pending')
                """
            ),
            {"k1": JOB_KIND_DR_WATCHLIST_MIN, "k2": JOB_KIND_DR_FULL},
        ).scalar()
        try:
            if int(n_running or 0) > 0:
                return None
        except Exception:
            pass

    # SQLite-friendly: seleccionar primero y hacer UPDATE condicional.
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id
                FROM company_reports
                WHERE COALESCE(job_status, 'queued') = 'queued'
                  AND COALESCE(status, 'pending') = 'pending'
                  AND COALESCE(job_kind, '') IN (:k1, :k2)
                ORDER BY COALESCE(report_enqueued_at, created_at) ASC, id ASC
                LIMIT 1
                """
            ),
            {"k1": JOB_KIND_DR_WATCHLIST_MIN, "k2": JOB_KIND_DR_FULL},
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


def _maybe_timeout(engine, report_id: int) -> bool:
    """
    Devuelve True si marcó timeout.
    """
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT job_started_at, job_phase FROM company_reports WHERE id=:rid"
            ),
            {"rid": int(report_id)},
        ).fetchone()
    if not row:
        return True
    started = row[0]
    if not started:
        return False
    try:
        # started es string sqlite "YYYY-MM-DD HH:MM:SS"
        dt = datetime.fromisoformat(str(started).replace(" ", "T"))
    except Exception:
        return False
    elapsed = (_utcnow() - dt).total_seconds()
    if elapsed <= _timeout_seconds():
        return False
    _mark_failed(
        engine,
        report_id,
        "Tiempo máximo superado sin resultado (posible bloqueo silencioso en el proveedor). "
        "Cuando el servidor corta la espera, genera el informe de nuevo.",
        kind="timeout",
    )
    return True


def run_once(app) -> bool:
    """
    Ejecuta un job si existe. Devuelve True si ejecutó algo.
    """
    from app import db
    from app.services.gemini_service import (
        GeminiServiceError,
        run_deep_research_report,
        resume_company_report_from_interaction_id,
    )
    from app.services.watchlist_ia_template import get_watchlist_ia_deep_brief, WATCHLIST_IA_REPORT_TITLE_DR_ROW

    engine = db.engine

    # Si quedó un job `running` tras reinicio del worker, reanudarlo antes de reclamar uno nuevo.
    with engine.connect() as conn:
        rr = conn.execute(
            text(
                """
                SELECT id, gemini_interaction_id
                FROM company_reports
                WHERE job_status = 'running'
                  AND COALESCE(job_kind, '') IN (:k1, :k2)
                  AND COALESCE(status, '') = 'processing'
                ORDER BY COALESCE(job_started_at, report_enqueued_at, created_at) ASC, id ASC
                LIMIT 1
                """
            ),
            {"k1": JOB_KIND_DR_WATCHLIST_MIN, "k2": JOB_KIND_DR_FULL},
        ).fetchone()
    if rr:
        rid_running = int(rr[0])
        iid_running = (rr[1] or "").strip()
        if iid_running:
            try:
                _update(engine, rid_running, job_phase="polling_provider")
                resume_company_report_from_interaction_id(rid_running)
            except Exception as e:
                _mark_failed(engine, rid_running, str(e), kind="provider")
            return True
        # Sin interaction_id: marcar failed y seguir
        _mark_failed(
            engine,
            rid_running,
            "Generación interrumpida antes de obtener respuesta de Gemini (sin interaction_id). Genera el informe de nuevo.",
            kind="orphan_no_iid",
        )
        return True

    rid = _claim_next_company_report_job(engine)
    if rid is None:
        return False

    ctx = _load_job_context(engine, rid)
    if not ctx:
        _mark_failed(engine, rid, "Job no encontrado", kind="internal")
        return True

    # Pasar a processing lo antes posible (compat con UI existente)
    _set_processing(engine, rid)

    # Preparar prompt según kind
    job_kind = (ctx.get("job_kind") or "").strip()
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
                import json

                points_list = json.loads(points_raw) if isinstance(points_raw, str) else []
            except Exception:
                points_list = []
        research_prompt_style = "full"

    aname = (ctx.get("name") or "Desconocida").strip()
    asym = (ctx.get("symbol") or "").strip()
    aisn = (ctx.get("isin") or "").strip()

    def on_interaction_created(iid: str) -> None:
        now = _utcnow()
        _update(
            engine,
            rid,
            gemini_interaction_id=(iid or "")[:100],
            job_phase="polling_provider",
            provider_last_status=None,
            provider_last_poll_at=now,
        )

    def on_status_update(st: str, msg: str) -> None:
        # `run_deep_research_report` llama a esto para mensajes de UI; persistimos lo mínimo.
        now = _utcnow()
        # Cada status_update corresponde a un poll (o avance de etapa) del provider.
        # Lo usamos como contador visible en UI.
        try:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE company_reports
                        SET provider_last_poll_at=:now,
                            provider_last_status=:st,
                            provider_poll_count=COALESCE(provider_poll_count, 0) + 1,
                            provider_last_error_msg=:em
                        WHERE id=:rid
                        """
                    ),
                    {
                        "now": now,
                        "st": (st or "")[:40],
                        # Guardar el último mensaje aunque no sea error (lo mostramos en UI)
                        "em": (msg or "")[:2000] if (msg or "").strip() else None,
                        "rid": int(rid),
                    },
                )
                conn.commit()
        except Exception:
            # Nunca romper el job por un fallo de telemetría
            pass

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
            # DR watchlist_min: tras completar, extraer y aplicar los 5 campos en Watchlist
            if job_kind == JOB_KIND_DR_WATCHLIST_MIN:
                try:
                    from app.services.watchlist_report_extract_service import (
                        apply_extracted_watchlist_fields,
                        extract_watchlist_fields_from_report_md,
                    )

                    extracted = extract_watchlist_fields_from_report_md(content or "")
                    apply_extracted_watchlist_fields(int(ctx.get("user_id") or 0), int(ctx.get("asset_id") or 0), extracted)
                except Exception:
                    logger.exception("watchlist extract/apply failed report_id=%s", rid)
            return True
        if status == "timeout":
            # No cortar por timeout aquí todavía: el worker decide por su propio reloj.
            # Si llegó 'timeout' desde gemini_service, lo tratamos como fallo del proveedor.
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
    """
    Bucle principal del worker.
    """
    idle = _sleep_seconds_idle()
    logger.info("company_report_jobs_worker: start (p95=%ss timeout=%ss idle_sleep=%ss)", _p95_seconds(), _timeout_seconds(), idle)
    with app.app_context():
        while True:
            try:
                did = run_once(app)
                if not did:
                    time.sleep(idle)
            except KeyboardInterrupt:
                raise
            except Exception:
                logger.exception("company_report_jobs_worker: loop error")
                time.sleep(2.0)

