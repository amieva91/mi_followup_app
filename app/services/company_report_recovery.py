"""
Informes ``company_reports`` en ``processing`` tras reinicio del proceso web.

- Sin ``gemini_interaction_id``: no hay nada que reanudar → ``failed``.
- Con ``gemini_interaction_id``: se lanza un hilo que vuelve a hacer polling a Gemini
  (:func:`resume_company_report_from_interaction_id`) para no perder trabajo que sigue en curso
  en el proveedor.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

_MSG_ORPHAN_NO_IID = (
    'Generación interrumpida antes de obtener respuesta de Gemini (sin interaction_id). '
    'Genera el informe de nuevo.'
)

_MSG_TIMEOUT_STALE = (
    'Tiempo máximo superado sin resultado (posible bloqueo silencioso en el proveedor). '
    'Cuando el servidor corta la espera, genera el informe de nuevo.'
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


def recover_processing_reports_after_restart(app, app_logger=None) -> None:
    """
    Tras ``systemctl restart`` ningún hilo en segundo plano sobrevive.

    - Informes con ``gemini_interaction_id``: reanudar polling en un hilo daemon.
    - Sin id (nunca llegó el callback de Gemini): marcar como fallido.
    - Audio en ``processing``: marcar fallido (la cola TTS no se reanuda aquí).
    """
    from app import db
    from app.models.company_report import CompanyReport

    log = app_logger or logger
    now = datetime.utcnow()

    rows = CompanyReport.query.filter(CompanyReport.status == 'processing').all()
    fail_no_iid = []
    resume_ids = []
    for r in rows:
        iid = (r.gemini_interaction_id or '').strip()
        if iid:
            resume_ids.append(r.id)
        else:
            fail_no_iid.append(r)

    for r in fail_no_iid:
        r.status = 'failed'
        r.error_msg = _MSG_ORPHAN_NO_IID
        r.completed_at = now

    audio_n = 0
    rows_a = CompanyReport.query.filter(CompanyReport.audio_status == 'processing').all()
    for r in rows_a:
        r.audio_status = 'failed'
        r.audio_error_msg = (_MSG_ORPHAN_NO_IID[:2000])
        # Si había un panel de progreso (pipeline completo), evitar que se quede "atascado" en loading.
        # Marcamos el paso TTS como error para que la UI muestre el fallo real y permita reintentar.
        try:
            ap_raw = getattr(r, 'audio_progress_json', None)
            if ap_raw and str(ap_raw).strip():
                ap = json.loads(str(ap_raw))
                steps = ap.get('steps') if isinstance(ap, dict) else None
                if isinstance(steps, list):
                    for st in steps:
                        if isinstance(st, dict) and st.get('id') == 'tts':
                            st['status'] = 'error'
                            st['error'] = _MSG_ORPHAN_NO_IID[:2000]
                    # Si email estaba pendiente, lo dejamos pendiente (pipeline no terminó).
                    ap['caption'] = ap.get('caption') or ''
                    r.audio_progress_json = json.dumps(ap, ensure_ascii=False)
        except Exception:
            # Best-effort: no bloquear recuperación por JSON corrupto.
            pass
        audio_n += 1

    if fail_no_iid or audio_n:
        db.session.commit()
        log.warning(
            'company_reports: %s informes sin interaction_id y %s audios marcados failed; '
            '%s informes con reanudación programada',
            len(fail_no_iid),
            audio_n,
            len(resume_ids),
        )
    elif resume_ids:
        log.info(
            'company_reports: reinicio — reanudando Deep Research para report_ids=%s',
            resume_ids,
        )

    for rid in resume_ids:

        def _run(rid_: int) -> None:
            try:
                with app.app_context():
                    from app.services.gemini_service import resume_company_report_from_interaction_id

                    resume_company_report_from_interaction_id(rid_)
            except Exception:
                log.exception('Deep Research resume: excepción no controlada report_id=%s', rid_)

        threading.Thread(target=_run, args=(rid,), daemon=True).start()