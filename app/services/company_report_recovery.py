"""
Recuperación de informes tras reinicios y estados inconsistentes.

- Deep Research sin ``gemini_interaction_id``: marcar fallido desde cualquier proceso que arranca Flask.
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

_MSG_TIMEOUT_STALE = (
    'Tiempo máximo superado sin resultado (posible bloqueo silencioso en el proveedor). '
    'Cuando el servidor corta la espera, genera el informe de nuevo.'
)


def _stale_queue_grace_seconds() -> int:
    """
    Margen extra para el reloj de «informe demasiado viejo»: tiempo posible en cola global
    (fair lock) antes de que Deep Research empiece de verdad. Sin esto, ``created_at`` antiguo
    + ~1 h de espera en ``pending`` hace que al pasar a ``processing`` se dispare un falso
    ``_MSG_TIMEOUT_STALE`` en minutos.
    """
    try:
        return max(0, int(str(os.environ.get('GEMINI_DR_STALE_QUEUE_GRACE_SECONDS', '7200')).strip()))
    except ValueError:
        return 7200


def expire_company_report_if_stale(report) -> bool:
    """
    Si el informe lleva demasiado en ``processing`` respecto al reloj de encolado/creación,
    marca ``failed`` (bloqueo silencioso probable en Gemini). No aplica a ``pending``: ese estado
    incluye espera legítima por el lock global, no consumo de presupuesto Deep Research.
    """
    from app import db
    from app.services.gemini_service import _get_deep_research_max_wait_seconds

    if report.status not in ('pending', 'processing'):
        return False
    if report.status == 'pending':
        return False
    created = report.created_at
    if not created:
        return False
    enq = getattr(report, 'report_enqueued_at', None)
    clock_start = max(created, enq) if enq else created
    max_sec = _get_deep_research_max_wait_seconds()
    grace = 180
    qgrace = _stale_queue_grace_seconds()
    threshold = datetime.utcnow() - timedelta(seconds=max_sec + grace + qgrace)
    if not (clock_start < threshold):
        return False
    logger.info(
        'company_reports: expire stale timeout report_id=%s clock_start=%s threshold_budget_s=%s',
        getattr(report, 'id', None),
        clock_start,
        max_sec + grace + qgrace,
    )
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

        if fail_no_iid:
            db.session.commit()
            log.warning(
                'company_reports: %s informes huérfanos (sin interaction_id); %s informes con reanudación programada',
                len(fail_no_iid),
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
        # Marker propio: este barrido NO debe quedar deshabilitado por el marker de
        # `recover_processing_reports_after_restart`. Si comparten marker, el segundo
        # se salta siempre durante los primeros 10 min del arranque.
        boot_marker = os.path.join(app.instance_path, "followup.recovery_pending_boot_marker")
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

        # Solo "solo informe": se identifica por NO tener full_pipeline en job_progress_json.
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
                ap = getattr(r, "job_progress_json", None)
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

            # Watchlist IA (Flash / Deep Research fila): estos informes no tienen plantilla (template_id=None),
            # por lo que `company_report_runner.run_report_only_by_id` no puede reconstruir `description/points`.
            # Si el hilo daemon muere antes de adquirir el lock, quedarían en `pending` para siempre.
            try:
                from app.services.watchlist_ia_template import (
                    WATCHLIST_IA_REPORT_TITLE_DR_ROW,
                    get_watchlist_ia_deep_brief,
                    is_watchlist_ia_report_title,
                )

                is_watchlist_ia = is_watchlist_ia_report_title(getattr(r, "template_title", None))
            except Exception:
                is_watchlist_ia = False

            if is_watchlist_ia:
                rid = int(r.id)
                aid = int(getattr(r, "asset_id", 0) or 0)
                uid = int(getattr(r, "user_id", 0) or 0)
                title = (getattr(r, "template_title", None) or "").strip()
                use_dr_row_title = title == WATCHLIST_IA_REPORT_TITLE_DR_ROW
                from app.services.valuation_mode_service import (
                    resolve_watchlist_valuation_mode_for_user_asset,
                )

                wl_mode = (
                    resolve_watchlist_valuation_mode_for_user_asset(uid, aid)
                    if uid and aid
                    else "general"
                )
                description, points, _ = get_watchlist_ia_deep_brief(
                    use_dr_row_title=use_dr_row_title, valuation_mode=wl_mode
                )

                def _run_watchlist_pending(rid_: int, uid_: int, aid_: int, desc_: str, pts_: list[str]) -> None:
                    try:
                        with app.app_context():
                            from app import db
                            from sqlalchemy import text
                            import threading as _threading

                            # Reclamar fila (pending -> processing) de forma atómica.
                            # Si ya no está pending, salimos (evita dobles ejecuciones).
                            with db.engine.connect() as conn:
                                res = conn.execute(
                                    text(
                                        # Importante: si el pending es viejo (horas), al pasar a processing
                                        # `expire_company_report_if_stale` podría marcarlo failed usando el
                                        # reloj de encolado. Reiniciamos `report_enqueued_at` al relanzar.
                                        "UPDATE company_reports SET status='processing', report_enqueued_at=:now "
                                        "WHERE id=:rid AND status='pending'"
                                    ),
                                    {
                                        "rid": int(rid_),
                                        "now": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                                    },
                                )
                                conn.commit()
                                if int(getattr(res, "rowcount", 0) or 0) == 0:
                                    return

                            # Re-ejecutar bajo la misma cola global (fair lock) y extracción a watchlist.
                            from app.services.company_report_deep_job import run_company_report_deep_research_job

                            def _worker() -> None:
                                run_company_report_deep_research_job(
                                    app,
                                    rid_,
                                    uid_,
                                    aid_,
                                    desc_,
                                    pts_,
                                    extra_prompt_suffix=None,
                                    post_watchlist_extract=True,
                                    research_prompt_style="watchlist_minimal",
                                    # Si el usuario pulsó 🔬 fila, forzamos Deep Research.
                                    watchlist_force_deep_research=use_dr_row_title,
                                )

                            _threading.Thread(target=_worker, daemon=True).start()
                    except Exception:
                        log.exception("watchlist pending recovery: excepción report_id=%s", rid_)

                threading.Thread(
                    target=_run_watchlist_pending,
                    args=(rid, uid, aid, description, points),
                    daemon=True,
                ).start()
                kicked += 1
                continue

            ap = getattr(r, "job_progress_json", None)
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
    y corta colas ``full_deliver`` en ``processing``.
    """
    from sqlalchemy import text

    from app import db

    log = app_logger or logger
    now = datetime.utcnow()
    msg_rep = (
        "Cola de informes limpiada manualmente (pendiente o en curso). "
        "Vuelve a lanzar la generación si aún lo necesitas."
    )
    msg_fd = (
        "Entrega todo-en-uno interrumpida (limpieza manual). "
        "El informe puede estar listo en la app; reenvía correo si hace falta."
    )
    out = {"reports_pending_failed": 0, "full_deliver_partial": 0}
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