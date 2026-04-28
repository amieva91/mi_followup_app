"""
Informes ``company_reports`` en estado ``processing`` sin proceso vivo (p. ej. tras reinicio
del servidor): marca como fallidos y permite liberar la UI sin esperas indefinidas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_MSG_RESTART_OR_ORPHAN = (
    'Generación interrumpida: no hay proceso activo (reinicio del servidor o tarea huérfana). '
    'Genera el informe de nuevo.'
)

_MSG_TIMEOUT_STALE = (
    'Tiempo máximo superado sin resultado (posible bloqueo silencioso en el proveedor). '
    'Genera el informe de nuevo o usa «Marcar como fallido» si sigue mostrándose en curso.'
)


def expire_company_report_if_stale(report) -> bool:
    """
    Si el informe lleva demasiado en ``pending``/``processing`` respecto a la fecha de creación,
    marca ``failed`` y hace commit. Devuelve True si hubo cambio persistido.
    """
    from app import db
    from app.services.gemini_service import _get_deep_research_max_wait_seconds

    if report.status not in ('pending', 'processing'):
        return False
    born = report.created_at
    if not born:
        return False
    max_sec = _get_deep_research_max_wait_seconds()
    grace = 180
    threshold = datetime.utcnow() - timedelta(seconds=max_sec + grace)
    if not (born < threshold):
        return False
    report.status = 'failed'
    report.error_msg = _MSG_TIMEOUT_STALE
    report.completed_at = datetime.utcnow()
    db.session.commit()
    return True


def fail_orphan_processing_reports_after_restart(app_logger=None) -> int:
    """
    Tras ``systemctl restart`` ningún hilo en segundo plano sobrevive: las filas ``processing``
    quedarían en bucle en la UI. Devuelve el número de filas actualizadas.
    """
    from app import db
    from app.models.company_report import CompanyReport

    log = app_logger or logger
    now = datetime.utcnow()
    n = 0
    rows = CompanyReport.query.filter(CompanyReport.status == 'processing').all()
    for r in rows:
        r.status = 'failed'
        r.error_msg = _MSG_RESTART_OR_ORPHAN
        r.completed_at = now
        n += 1
    audio_n = 0
    rows_a = CompanyReport.query.filter(CompanyReport.audio_status == 'processing').all()
    for r in rows_a:
        r.audio_status = 'failed'
        msg = _MSG_RESTART_OR_ORPHAN[:2000]
        r.audio_error_msg = msg
        audio_n += 1
    if n or audio_n:
        db.session.commit()
        log.warning(
            'company_reports: %s informes y %s audios en processing marcados failed (huérfanos tras arranque)',
            n,
            audio_n,
        )
    return n + audio_n

