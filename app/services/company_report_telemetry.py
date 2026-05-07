"""
Telemetría unificada de informes largos (Deep Research / pipelines).

- Persistencia desde worker, hilo ``full_deliver`` y (futuro) otros job kinds.
- Fragmentos JSON reutilizables por las rutas de API / detalle.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text

# Misma base que el worker (`company_report_jobs_worker._p95_seconds`).
def dr_p95_seconds() -> int:
    raw = os.environ.get("FOLLOWUP_DR_P95_SECONDS", "").strip()
    if not raw:
        return 30 * 60
    try:
        return max(60, int(raw))
    except ValueError:
        return 30 * 60


def dr_timeout_seconds() -> int:
    return int(dr_p95_seconds() * 1.5)


def iso_utc_z(v: Any) -> Optional[str]:
    try:
        if not v:
            return None
        s = v.isoformat()
        if s.endswith("Z") or "+" in s:
            return s
        return s + "Z"
    except Exception:
        return None


def persist_provider_poll(
    engine,
    report_id: int,
    provider_status: str,
    provider_message: Optional[str] = None,
    *,
    job_phase: Optional[str] = None,
    bump_poll: bool = True,
) -> None:
    """
    Actualiza columnas de telemetría del proveedor (y opcionalmente fase del job).
    Diseñado para llamarse desde callbacks de ``run_deep_research_report``.
    """
    now = datetime.utcnow()
    if provider_message is not None and str(provider_message).strip():
        msg = str(provider_message).strip()[:2000]
    else:
        msg = None
    st = (provider_status or "")[:40]
    rid = int(report_id)

    extra = ""
    params: dict[str, Any] = {"now": now, "st": st, "em": msg, "rid": rid}
    if bump_poll:
        extra = ", provider_poll_count=COALESCE(provider_poll_count, 0) + 1"
    if job_phase is not None:
        extra += ", job_phase=:jp"
        params["jp"] = str(job_phase)[:80]

    sql = text(
        f"""
        UPDATE company_reports SET
          provider_last_poll_at=:now,
          provider_last_status=:st,
          provider_last_error_msg=:em
          {extra}
        WHERE id=:rid
        """
    )

    try:
        with engine.connect() as conn:
            conn.execute(sql, params)
            conn.commit()
    except Exception:
        pass


def persist_interaction_created(engine, report_id: int, interaction_id: str) -> None:
    """Tras obtener ``interaction_id`` de Gemini (primer hito durable)."""
    now = datetime.utcnow()
    iid = str(interaction_id or "")[:100]
    rid = int(report_id)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE company_reports
                    SET gemini_interaction_id=:iid,
                        job_phase='polling_provider',
                        provider_last_poll_at=:now,
                        provider_last_status=NULL,
                        provider_last_error_msg=NULL
                    WHERE id=:rid AND status='processing'
                    """
                ),
                {"iid": iid, "now": now, "rid": rid},
            )
            conn.commit()
    except Exception:
        pass


def job_and_provider_json(report: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Diccionarios ``job`` y ``provider`` alineados con ``/api/reports/<id>/status``.
    ``report`` es un modelo ``CompanyReport`` (o compatible).
    """
    job_started_at = getattr(report, "job_started_at", None)
    elapsed_s = None
    try:
        if job_started_at:
            elapsed_s = int((datetime.utcnow() - job_started_at).total_seconds())
    except Exception:
        elapsed_s = None

    p95_s = dr_p95_seconds()
    timeout_s = dr_timeout_seconds()
    st = getattr(report, "status", None)
    possible_blocked = bool(elapsed_s is not None and elapsed_s >= p95_s and st == "processing")
    timed_out = bool(elapsed_s is not None and elapsed_s >= timeout_s and st == "processing")

    job = {
        "kind": getattr(report, "job_kind", None),
        "status": getattr(report, "job_status", None),
        "phase": getattr(report, "job_phase", None),
        "started_at": iso_utc_z(getattr(report, "job_started_at", None)),
        "finished_at": iso_utc_z(getattr(report, "job_finished_at", None)),
        "elapsed_s": elapsed_s,
        "p95_s": p95_s,
        "timeout_s": timeout_s,
        "possible_blocked": possible_blocked,
        "timed_out": timed_out,
    }
    provider = {
        "last_status": getattr(report, "provider_last_status", None),
        "last_poll_at": iso_utc_z(getattr(report, "provider_last_poll_at", None)),
        "poll_count": getattr(report, "provider_poll_count", None),
        "last_http_status": getattr(report, "provider_last_http_status", None),
        "last_error_kind": getattr(report, "provider_last_error_kind", None),
        "last_error_msg": getattr(report, "provider_last_error_msg", None),
        "create_attempt": getattr(report, "provider_create_attempt", None),
        "next_retry_at": iso_utc_z(getattr(report, "provider_next_retry_at", None)),
        "interaction_id": getattr(report, "gemini_interaction_id", None),
    }
    return job, provider


def status_visible_for_report(report: Any) -> str:
    """Misma regla que la API de estado (cola DB-backed)."""
    status_visible = getattr(report, "status", None) or ""
    try:
        js = getattr(report, "job_status", None)
        if js == "queued" and getattr(report, "status", None) == "processing":
            return "pending"
    except Exception:
        pass
    return str(status_visible)


def sync_full_deliver_job_terminal(engine: Any, report_id: int | Any) -> None:
    """Alinea ``job_status`` / ``job_phase`` con estado final tras tail async o commit final."""
    import logging as _logging

    _log = _logging.getLogger(__name__)
    rid: int | None = None
    try:
        rid = int(report_id)
    except Exception:
        return
    now = datetime.utcnow()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT status, delivery_phase_status, job_kind
                    FROM company_reports WHERE id=:rid
                    """
                ),
                {"rid": rid},
            ).fetchone()
        if not row:
            return
        st, dps, jk = row[0], row[1], (row[2] or "").strip()
        if jk != "full_deliver":
            return
        if st == "failed":
            with engine.connect() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE company_reports SET
                          job_status='failed',
                          job_phase='failed',
                          job_finished_at=COALESCE(job_finished_at, :now)
                        WHERE id=:rid
                        """
                    ),
                    {"now": now, "rid": rid},
                )
                conn.commit()
            return
        if st == "completed" and (dps or "") == "completed":
            with engine.connect() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE company_reports SET
                          job_status='completed',
                          job_phase='completed',
                          job_finished_at=COALESCE(job_finished_at, :now)
                        WHERE id=:rid
                        """
                    ),
                    {"now": now, "rid": rid},
                )
                conn.commit()
            return
        if st == "completed" and dps in ("partial", "failed"):
            jp = str(dps).strip().lower()
            if jp not in ("partial", "failed"):
                jp = "partial"
            with engine.connect() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE company_reports SET
                          job_status='completed',
                          job_phase=COALESCE(job_phase,:jp),
                          job_finished_at=COALESCE(job_finished_at, :now)
                        WHERE id=:rid
                        """
                    ),
                    {"now": now, "rid": rid, "jp": jp[:80]},
                )
                conn.commit()
    except Exception:
        _log.exception("sync_full_deliver_job_terminal rid=%s", rid)
