"""
Cola global de trabajos largos sobre ``company_reports`` (informe y todo-en-uno).

La ordenación debe coincidir con la que usa la UI (posición #1 / #2) y con
:func:`app.background_tasks_lock.background_tasks_lock` cuando ``fair_report_id`` está fijado.

Debug remoto (logs): ``FOLLOWUP_REPORT_QUEUE_DEBUG=1`` activa trazas INFO con orden de cola
y cabeza global al adquirir el lock justo y durante esperas (throttle).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from sqlalchemy import bindparam, text

from app import db

logger = logging.getLogger(__name__)


def is_report_queue_debug() -> bool:
    """Logs extra de cola + fair lock (ver docstring del módulo)."""
    raw = os.environ.get('FOLLOWUP_REPORT_QUEUE_DEBUG', '')
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


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


def _row_active_queue_sort_key(row: dict) -> datetime | None:
    r_st = row.get("status")
    dm = row.get("delivery_mode")
    dps = row.get("delivery_phase_status")
    if r_st == "completed" and dm == "full_deliver" and (dps == "processing" or dps is None):
        return _to_utc_dt(row.get("completed_at") or row.get("report_enqueued_at") or row.get("created_at"))
    if r_st in ("pending", "processing"):
        return _to_utc_dt(row.get("report_enqueued_at") or row.get("created_at"))
    return None


def sorted_active_queue_rows() -> list[tuple[datetime, int]]:
    """Lista (tiempo_encolado, id) ordenada; define la cola global para UI y fair lock."""
    try:
        res = db.session.execute(
            text(
                """
                SELECT id, status,
                       report_enqueued_at, created_at,
                       delivery_mode, delivery_phase_status, completed_at
                FROM company_reports
                """
            )
        )
        pairs: list[tuple[datetime, int]] = []
        for r in res.mappings():
            row = dict(r)
            k = _row_active_queue_sort_key(row)
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


def queue_metrics_for_report_id(report_id: int) -> tuple[int | None, int]:
    """(posición 1-based, total) o (None, total) si este id no está en la cola activa."""
    rid = int(report_id)
    pairs = sorted_active_queue_rows()
    n = len(pairs)
    for i, (_k, qid) in enumerate(pairs):
        if qid == rid:
            return i + 1, n
    return None, n


def queue_metrics_for_report(report) -> tuple[int | None, int]:
    """(posición 1-based, total) o (None, total) si este informe no espera."""
    return queue_metrics_for_report_id(report.id)


def log_global_queue_snapshot(reason: str) -> None:
    """
    Una línea INFO por ítem en orden de cola (id, asset, status, encolado, título).
    Solo efecto si :func:`is_report_queue_debug` es True.
    """
    if not is_report_queue_debug():
        return
    pairs = sorted_active_queue_rows()
    if not pairs:
        logger.info('REPORT_QUEUE_DEBUG %s | global_queue=empty', reason)
        return
    ids = [qid for _k, qid in pairs]
    try:
        stmt = text(
            """
            SELECT id, asset_id, status, template_title, report_enqueued_at, created_at
            FROM company_reports
            WHERE id IN :ids
            """
        ).bindparams(bindparam('ids', expanding=True))
        res = db.session.execute(stmt, {'ids': ids}).mappings().all()
    except Exception:
        logger.exception('REPORT_QUEUE_DEBUG %s | snapshot query failed', reason)
        return
    by_id = {int(r['id']): dict(r) for r in res}
    parts: list[str] = []
    for i, (_k, qid) in enumerate(pairs, start=1):
        r = by_id.get(qid, {})
        title = (r.get('template_title') or '')[:48]
        parts.append(
            f"#{i}:id={qid}:a={r.get('asset_id')}:st={r.get('status')}"
            f":enq={r.get('report_enqueued_at')}:t={title!r}"
        )
    logger.info(
        'REPORT_QUEUE_DEBUG %s | n=%d | %s',
        reason,
        len(pairs),
        ' | '.join(parts),
    )
