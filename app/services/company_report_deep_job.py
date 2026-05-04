"""
Ejecución en segundo plano de informes Deep Research (CompanyReport).
Un solo hilo puede procesar varios informes en serie para no saturar la API.
"""
import logging
import traceback
from datetime import datetime

from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)

# Texto añadido al prompt de Deep Research cuando se lanza desde la watchlist (todos los assets).
WATCHLIST_MANUAL_FIELDS_PROMPT = """
## Datos para formulario watchlist (solo si la investigación lo respalda con fuentes)

Al final del informe, incluye una sección breve **"Datos watchlist (extracción)"** donde, para cada campo,
indiques el valor **solo si aparece de forma clara en fuentes fiables** de tu investigación; si no, escribe exactamente `no disponible`.

Formato esperado por la aplicación (nombres de campo internos):

| Campo | Significado | Formato si hay dato |
|-------|-------------|---------------------|
| next_earnings_date | Próxima fecha de presentación de resultados (earnings) | Fecha ISO `YYYY-MM-DD` |
| per_ntm | PER o P/E NTM | Número decimal (ej. 18.5), sin texto |
| ntm_dividend_yield | Dividend yield NTM | Número en % (ej. 2.3 para 2,3%) |
| eps | EPS (beneficio por acción) | Número decimal en moneda del activo |
| cagr_revenue_yoy | CAGR ingresos interanual | Número en % (ej. 8.0) |

No inventes cifras: si no hay fuente explícita, `no disponible` para ese campo.
"""


def run_company_report_deep_research_job(
    app,
    report_id,
    user_id,
    asset_id,
    description,
    points,
    extra_prompt_suffix=None,
    post_watchlist_extract=False,
):
    """
    Hilo: actualiza un CompanyReport (pending → processing → completed/failed).
    Usa conexión raw SQL para no depender de sesión ORM del hilo principal.
    """
    from app import db
    from app.background_tasks_lock import background_tasks_lock
    from app.services.gemini_service import run_deep_research_report, GeminiServiceError

    # Misma cola justa que informes desde ficha (company_report_queue + flock).
    with app.app_context(), background_tasks_lock(app, fair_report_id=report_id):
        engine = db.engine

        def _update_status(st, content_val=None, error_val=None):
            now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            with engine.connect() as conn:
                conn.execute(
                    text(
                        """
                            UPDATE company_reports SET status = :st, completed_at = :now
                            , content = :content, error_msg = :error WHERE id = :rid
                        """
                    ),
                    {
                        'st': st,
                        'now': now_str,
                        'content': content_val,
                        'error': error_val,
                        'rid': report_id,
                    },
                )
                conn.commit()

        try:
            with engine.connect() as conn:
                r = conn.execute(
                    text(
                        "UPDATE company_reports SET status = 'processing' WHERE id = :rid"
                    ),
                    {'rid': report_id},
                )
                conn.commit()
                if r.rowcount == 0:
                    return
        except Exception as e:
            try:
                _update_status('failed', error_val=str(e))
            except Exception:
                pass
            logger.exception('Error pasando report a processing: %s', e)
            return

        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text('SELECT name, symbol, isin FROM assets WHERE id = :aid'),
                    {'aid': asset_id},
                ).fetchone()
            if not row:
                _update_status('failed', error_val='Asset no encontrado')
                return
            aname = row[0] or 'Desconocida'
            asym = row[1] or ''
            aisn = row[2] or ''

            status, content = run_deep_research_report(
                aname,
                asym,
                aisn,
                description,
                points,
                extra_prompt_suffix=extra_prompt_suffix,
            )

            content_val = content if status == 'completed' else None
            error_val = content if status == 'failed' else None
            _update_status(status, content_val=content_val, error_val=error_val)

            if status == 'completed' and post_watchlist_extract and content_val:
                try:
                    from app.services.watchlist_report_extract_service import (
                        try_apply_report_to_watchlist,
                    )

                    try_apply_report_to_watchlist(user_id, asset_id, content_val)
                except Exception as ex:
                    logger.exception(
                        "post_watchlist_extract falló asset_id=%s: %s", asset_id, ex
                    )

            if status == 'completed':
                with engine.connect() as conn:
                    cnt = conn.execute(
                        text(
                            'SELECT COUNT(*) FROM company_reports WHERE user_id = :uid AND asset_id = :aid'
                        ),
                        {'uid': user_id, 'aid': asset_id},
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
                                {'uid': user_id, 'aid': asset_id, 'lim': lim},
                            ).fetchall()
                        ]
                        if ids:
                            stmt = text('DELETE FROM company_reports WHERE id IN :ids').bindparams(
                                bindparam('ids', expanding=True)
                            )
                            conn.execute(stmt, {'ids': ids})
                    conn.commit()
        except GeminiServiceError as e:
            try:
                _update_status('failed', error_val=str(e))
            except Exception:
                pass
        except Exception as e:
            logger.exception('Error en Deep Research job: %s', e)
            try:
                _update_status('failed', error_val=str(e))
            except Exception:
                pass
            traceback.print_exc()


def start_company_report_background_thread(
    app, report_id, user_id, asset_id, description, points, extra_prompt_suffix=None
):
    """Un informe en un hilo daemon (comportamiento histórico de /asset/.../reports/generate)."""
    import threading

    t = threading.Thread(
        target=run_company_report_deep_research_job,
        kwargs={
            'app': app,
            'report_id': report_id,
            'user_id': user_id,
            'asset_id': asset_id,
            'description': description,
            'points': points,
            'extra_prompt_suffix': extra_prompt_suffix,
            'post_watchlist_extract': False,
        },
        daemon=True,
    )
    t.start()


def start_watchlist_batch_reports_thread(app, job_id, jobs):
    """
    Varios informes en un solo hilo, en serie (menos carga en API Gemini).
    Actualiza WatchlistAiJob para progreso en UI.

    jobs: lista de dicts con keys report_id, user_id, asset_id, description, points
    """
    import threading

    def worker():
        with app.app_context():
            from app import db
            from app.models import Asset, WatchlistAiJob

            job_row = WatchlistAiJob.query.get(job_id)
            if not job_row:
                return
            total = len(jobs)
            job_row.total = total
            job_row.completed_count = 0
            job_row.status = "running"
            job_row.error_message = None
            job_row.updated_at = datetime.utcnow()
            db.session.commit()

            try:
                for idx, job in enumerate(jobs):
                    aid = job["asset_id"]
                    asset = Asset.query.get(aid)
                    label = (
                        (asset.name or asset.symbol or str(aid))[:200]
                        if asset
                        else str(aid)
                    )
                    job_row.current_asset_id = aid
                    job_row.current_asset_label = label
                    job_row.completed_count = idx
                    job_row.updated_at = datetime.utcnow()
                    db.session.commit()

                    run_company_report_deep_research_job(
                        app,
                        job["report_id"],
                        job["user_id"],
                        aid,
                        job["description"],
                        job["points"],
                        extra_prompt_suffix=WATCHLIST_MANUAL_FIELDS_PROMPT,
                        post_watchlist_extract=True,
                    )

                    job_row.completed_count = idx + 1
                    job_row.updated_at = datetime.utcnow()
                    db.session.commit()

                job_row.status = "completed"
                job_row.current_asset_id = None
                job_row.current_asset_label = None
                job_row.updated_at = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                logger.exception("watchlist batch job %s: %s", job_id, e)
                try:
                    job_row = WatchlistAiJob.query.get(job_id)
                    if job_row:
                        job_row.status = "failed"
                        job_row.error_message = str(e)[:2000]
                        job_row.updated_at = datetime.utcnow()
                        db.session.commit()
                except Exception:
                    pass

    threading.Thread(target=worker, daemon=True).start()
