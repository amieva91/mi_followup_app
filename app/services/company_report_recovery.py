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
import os

logger = logging.getLogger(__name__)

_MSG_ORPHAN_NO_IID = (
    'Generación interrumpida antes de obtener respuesta de Gemini (sin interaction_id). '
    'Genera el informe de nuevo.'
)

# El TTS no usa interaction_id; este mensaje evita confundir al usuario cuando falla solo el audio.
_MSG_AUDIO_ORPHAN = (
    'La generación de audio se interrumpió (reinicio del servidor o fin del worker). '
    'Pulsa «Regenerar audio».'
)

_MSG_TIMEOUT_STALE = (
    'Tiempo máximo superado sin resultado (posible bloqueo silencioso en el proveedor). '
    'Cuando el servidor corta la espera, genera el informe de nuevo.'
)


def _stale_audio_queued_seconds() -> int:
    """Segundos tras los cuales un ``audio_status=queued`` (informe ya OK, sin WAV) se considera abandonado."""
    try:
        return max(300, int(str(os.environ.get('STALE_AUDIO_QUEUED_SECONDS', '3600')).strip()))
    except ValueError:
        return 3600


def expire_stale_audio_queued_rows(app_logger=None) -> int:
    """
    Informe ya ``completed``, audio en ``queued``, sin fichero y con antigüedad de encolado alta:
    no hay worker real esperando — ensucian la cola global y la numeración.

    Marca ``audio_status=failed`` con mensaje claro para que el usuario pulse «Regenerar audio».
    """
    from app import db
    from sqlalchemy import text

    log = app_logger or logger
    sec = _stale_audio_queued_seconds()
    cutoff = datetime.utcnow() - timedelta(seconds=sec)
    msg = (
        'La petición de audio quedó demasiado tiempo en cola sin ejecutarse. '
        'Pulsa «Regenerar audio».'
    )
    try:
        res = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET audio_status = 'failed', audio_error_msg = :msg
                WHERE audio_status = 'queued'
                  AND status = 'completed'
                  AND (audio_path IS NULL OR TRIM(COALESCE(audio_path, '')) = '')
                  AND COALESCE(audio_enqueued_at, created_at) < :cutoff
                """
            ),
            {'cutoff': cutoff, 'msg': msg[:8000]},
        )
        n = int(getattr(res, 'rowcount', 0) or 0)
        if n:
            db.session.commit()
            log.info('company_reports: expiradas %s peticiones de audio encoladas obsoletas (cutoff %ss)', n, sec)
        else:
            db.session.rollback()
        return n
    except Exception:
        db.session.rollback()
        log.exception('expire_stale_audio_queued_rows: error')
        return 0


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

    # Guard de seguridad:
    # - Gunicorn puede recrear workers durante el día (sin systemctl restart).
    # - Esta función se llama en init por worker; NO debemos marcar como failed
    #   informes recién creados que aún están corriendo y todavía no han persistido interaction_id.
    # - Además, evitamos que varios workers hagan el barrido a la vez.
    try:
        import fcntl  # type: ignore
    except Exception:
        fcntl = None  # type: ignore

    lock_fp = None
    if fcntl is not None:
        try:
            os.makedirs(app.instance_path, exist_ok=True)
            lock_path = os.path.join(app.instance_path, 'followup.recovery_company_reports.lock')
            lock_fp = open(lock_path, 'a+')
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        except Exception:
            lock_fp = None

    log = app_logger or logger
    now = datetime.utcnow()
    # Ejecutar solo una vez por arranque del servicio (no por worker gunicorn).
    # Si varios workers se inician secuencialmente, evitar que uno marque como huérfano
    # un informe que otro worker acaba de relanzar y aún no ha persistido interaction_id.
    boot_marker = os.path.join(app.instance_path, "followup.recovery_boot_marker")
    try:
        if os.path.exists(boot_marker):
            try:
                mtime = datetime.utcfromtimestamp(os.path.getmtime(boot_marker))
                if (now - mtime).total_seconds() < 600:
                    return
            except Exception:
                # si no podemos leer mtime, seguimos
                pass
        try:
            with open(boot_marker, "w", encoding="utf-8") as fp:
                fp.write(now.isoformat())
        except Exception:
            pass
    except Exception:
        pass
    # No tocar filas "jóvenes" (evita falsos positivos durante arranque/recycle de worker).
    # 3 minutos suele ser suficiente para que gemini_interaction_id se persista si el hilo está vivo.
    min_age_seconds = 180
    min_age_threshold = now - timedelta(seconds=min_age_seconds)

    try:
        rows = CompanyReport.query.filter(CompanyReport.status == 'processing').all()
        fail_no_iid = []
        resume_ids = []
        for r in rows:
            # Solo considerar como "huérfano" si es suficientemente antiguo.
            if getattr(r, 'created_at', None) and r.created_at > min_age_threshold:
                continue
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
        tail_resume_ids: list[int] = []
        rows_a = CompanyReport.query.filter(CompanyReport.audio_status == 'processing').all()
        for r in rows_a:
            if getattr(r, 'created_at', None) and r.created_at > min_age_threshold:
                continue
            if getattr(r, 'delivery_mode', None) == 'full_deliver' and (r.status or '') == 'completed':
                tail_resume_ids.append(int(r.id))
                continue
            r.audio_status = 'failed'
            r.audio_error_msg = (_MSG_AUDIO_ORPHAN[:2000])
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
                                st['error'] = _MSG_AUDIO_ORPHAN[:2000]
                        ap['caption'] = ap.get('caption') or ''
                        r.audio_progress_json = json.dumps(ap, ensure_ascii=False)
            except Exception:
                pass
            audio_n += 1

        if fail_no_iid or audio_n:
            db.session.commit()
            log.warning(
                'company_reports: %s informes huérfanos (sin interaction_id) y %s audios marcados failed; '
                '%s informes con reanudación programada (si procede)',
                len(fail_no_iid),
                audio_n,
                len(resume_ids),
            )
        elif resume_ids:
            log.info(
                'company_reports: recuperación — reanudando Deep Research para report_ids=%s',
                resume_ids,
            )
    finally:
        try:
            if lock_fp is not None:
                try:
                    if fcntl is not None:
                        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lock_fp.close()
        except Exception:
            pass

    for rid in resume_ids:

        def _run(rid_: int) -> None:
            try:
                with app.app_context():
                    from app.services.gemini_service import resume_company_report_from_interaction_id

                    resume_company_report_from_interaction_id(rid_)
            except Exception:
                log.exception('Deep Research resume: excepción no controlada report_id=%s', rid_)

        threading.Thread(target=_run, args=(rid,), daemon=True).start()

    for rid in tail_resume_ids:
        try:
            from app.services.full_deliver_continuation import schedule_full_delivery_continuation

            schedule_full_delivery_continuation(app, rid)
        except Exception:
            log.exception('full_deliver: reanudación tras audio processing report_id=%s', rid)


def recover_stuck_pending_reports(app, app_logger=None) -> None:
    """
    Reclamación best-effort de informes `pending` que se quedaron en cola sin hilo vivo.

    Esto puede ocurrir si el worker de Gunicorn que creó el hilo daemon se recicla antes
    de adquirir el lock global. En vez de dejar el informe en `pending` para siempre,
    lo relanzamos en background.
    """
    from app.models.company_report import CompanyReport

    log = app_logger or logger
    now = datetime.utcnow()
    min_age_seconds = 180
    threshold = now - timedelta(seconds=min_age_seconds)

    # Reusar el mismo lock file (misma intención: barrido 1 vez).
    try:
        import fcntl  # type: ignore
    except Exception:
        fcntl = None  # type: ignore

    lock_fp = None
    if fcntl is not None:
        try:
            os.makedirs(app.instance_path, exist_ok=True)
            lock_path = os.path.join(app.instance_path, "followup.recovery_company_reports.lock")
            lock_fp = open(lock_path, "a+")
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        except Exception:
            lock_fp = None

    try:
        # Mismo marker: si recovery ya corrió en este arranque, no repetir barridos.
        boot_marker = os.path.join(app.instance_path, "followup.recovery_boot_marker")
        try:
            if os.path.exists(boot_marker):
                try:
                    mtime = datetime.utcfromtimestamp(os.path.getmtime(boot_marker))
                    if (now - mtime).total_seconds() < 600:
                        return
                except Exception:
                    pass
            try:
                with open(boot_marker, "w", encoding="utf-8") as fp:
                    fp.write(now.isoformat())
            except Exception:
                pass
        except Exception:
            pass

        # Solo "solo informe": se identifica por NO tener full_pipeline en audio_progress_json.
        rows = (
            CompanyReport.query.filter(CompanyReport.status == "pending")
            .filter(CompanyReport.created_at < threshold)
            .order_by(CompanyReport.created_at.asc())
            .limit(10)
            .all()
        )
        if not rows:
            return
        kicked = 0
        for r in rows:
            is_fd = getattr(r, "delivery_mode", None) == "full_deliver"
            if not is_fd:
                ap = getattr(r, "audio_progress_json", None)
                if ap and str(ap).strip() and "full_pipeline" in str(ap):
                    is_fd = True
            if is_fd:
                rid = int(r.id)

                def _run_full(rid_: int) -> None:
                    try:
                        with app.app_context():
                            from app.services.full_deliver_continuation import run_full_deliver_pending_recovery

                            run_full_deliver_pending_recovery(app, rid_)
                    except Exception:
                        log.exception(
                            "full_deliver pending recovery: excepción report_id=%s",
                            rid_,
                        )

                threading.Thread(target=_run_full, args=(rid,), daemon=True).start()
                kicked += 1
                continue

            ap = getattr(r, "audio_progress_json", None)
            is_full = False
            if ap and str(ap).strip():
                try:
                    obj = json.loads(str(ap))
                    is_full = bool(isinstance(obj, dict) and obj.get("full_pipeline"))
                except Exception:
                    is_full = False
            if is_full:
                continue

            rid = int(r.id)

            def _run(rid_: int) -> None:
                try:
                    from app.services.company_report_runner import run_report_only_by_id

                    run_report_only_by_id(app, rid_)
                except Exception:
                    log.exception("Deep Research runner: excepción no controlada report_id=%s", rid_)

            threading.Thread(target=_run, args=(rid,), daemon=True).start()
            kicked += 1

        if kicked:
            log.warning(
                "company_reports: %s informes pending atascados relanzados (>= %ss)",
                kicked,
                min_age_seconds,
            )
    finally:
        try:
            if lock_fp is not None:
                try:
                    if fcntl is not None:
                        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lock_fp.close()
        except Exception:
            pass


def clean_company_report_queues(app_logger=None) -> dict:
    """
    Operación de mantenimiento: marca como fallidos informes ``pending``/``processing``,
    audios ``queued`` huérfanos, y corta colas ``full_deliver`` en ``processing``.
    """
    from sqlalchemy import text

    from app import db

    log = app_logger or logger
    now = datetime.utcnow()
    msg_rep = (
        "Cola de informes limpiada manualmente (pendiente o en curso). "
        "Vuelve a lanzar la generación si aún lo necesitas."
    )
    msg_au = (
        "Cola de audio limpiada manualmente. Pulsa «Regenerar audio» si quieres un nuevo fichero."
    )
    msg_fd = (
        "Entrega todo-en-uno interrumpida (limpieza manual). "
        "El informe puede estar listo en la app; reenvía correo o regenera audio si hace falta."
    )
    out = {"reports_pending_failed": 0, "audio_queued_failed": 0, "full_deliver_partial": 0}
    try:
        r1 = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET status = 'failed', error_msg = :msg, completed_at = :now
                WHERE status IN ('pending', 'processing')
                """
            ),
            {"msg": msg_rep[:8000], "now": now},
        )
        out["reports_pending_failed"] = int(getattr(r1, "rowcount", 0) or 0)

        r2 = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET audio_status = 'failed', audio_error_msg = :msg
                WHERE audio_status = 'queued' AND status = 'completed'
                """
            ),
            {"msg": msg_au[:8000]},
        )
        out["audio_queued_failed"] = int(getattr(r2, "rowcount", 0) or 0)

        r3 = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET delivery_phase_status = 'partial', error_msg = :msg
                WHERE delivery_mode = 'full_deliver'
                  AND (delivery_phase_status = 'processing' OR delivery_phase_status IS NULL)
                  AND status = 'completed'
                """
            ),
            {"msg": msg_fd[:8000]},
        )
        out["full_deliver_partial"] = int(getattr(r3, "rowcount", 0) or 0)

        db.session.commit()
        log.warning("company_reports: limpieza manual %s", out)
    except Exception:
        db.session.rollback()
        log.exception("clean_company_report_queues")
        raise
    return out