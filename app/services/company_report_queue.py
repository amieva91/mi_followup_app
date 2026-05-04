"""
Cola global de trabajos largos sobre ``company_reports`` (informe, todo-en-uno, audio).

La ordenación debe coincidir con la que usa la UI (posición #1 / #2) y con
:func:`app.background_tasks_lock.background_tasks_lock` cuando ``fair_report_id`` está fijado.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from app import db
from app.services.company_report_recovery import _stale_audio_queued_seconds

logger = logging.getLogger(__name__)


def _to_utc_dt(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))
        except Exception:
            return None
    return None


def _stale_audio_queued_cutoff_utc() -> datetime:
    return datetime.utcnow() - timedelta(seconds=_stale_audio_queued_seconds())


def _row_is_stale_audio_queued(row: dict, cutoff: datetime) -> bool:
    if row.get("audio_status") != "queued" or row.get("status") != "completed":
        return False
    path = (row.get("audio_path") or "").strip()
    if path:
        return False
    t = _to_utc_dt(row.get("audio_enqueued_at") or row.get("created_at"))
    if not t:
        return False
    return t < cutoff


def _row_active_queue_sort_key(row: dict, cutoff: datetime) -> datetime | None:
    a_st = row.get("audio_status")
    r_st = row.get("status")
    dm = row.get("delivery_mode")
    dps = row.get("delivery_phase_status")
    if a_st in ("queued", "processing"):
        if a_st == "queued" and _row_is_stale_audio_queued(row, cutoff):
            pass
        else:
            return _to_utc_dt(row.get("audio_enqueued_at") or row.get("created_at"))
    if r_st == "completed" and dm == "full_deliver" and (dps == "processing" or dps is None):
        return _to_utc_dt(row.get("completed_at") or row.get("report_enqueued_at") or row.get("created_at"))
    if r_st in ("pending", "processing"):
        return _to_utc_dt(row.get("report_enqueued_at") or row.get("created_at"))
    return None


def sorted_active_queue_rows() -> list[tuple[datetime, int]]:
    """Lista (tiempo_encolado, id) ordenada; define la cola global para UI y fair lock."""
    cutoff = _stale_audio_queued_cutoff_utc()
    try:
        res = db.session.execute(
            text(
                """
                SELECT id, audio_status, status, audio_path,
                       audio_enqueued_at, report_enqueued_at, created_at,
                       delivery_mode, delivery_phase_status, completed_at
                FROM company_reports
                """
            )
        )
        pairs: list[tuple[datetime, int]] = []
        for r in res.mappings():
            row = dict(r)
            k = _row_active_queue_sort_key(row, cutoff)
            if k is not None:
                pairs.append((k, int(row["id"])))
        pairs.sort(key=lambda x: (x[0], x[1]))
        return pairs
    except Exception:
        logger.exception("sorted_active_queue_rows")
        return []


def first_in_global_report_queue() -> int | None:
    pairs = sorted_active_queue_rows()
    return int(pairs[0][1]) if pairs else None


def report_id_in_active_global_queue(report_id: int) -> bool:
    rid = int(report_id)
    return any(qid == rid for _k, qid in sorted_active_queue_rows())


def queue_metrics_for_report(report) -> tuple[int | None, int]:
    """(posición 1-based, total) o (None, total) si este informe no espera."""
    rid = int(report.id)
    pairs = sorted_active_queue_rows()
    n = len(pairs)
    for i, (_k, qid) in enumerate(pairs):
        if qid == rid:
            return i + 1, n
    return None, n
