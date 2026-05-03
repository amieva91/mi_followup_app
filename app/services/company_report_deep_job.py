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
):
    """
    Hilo: actualiza un CompanyReport (pending → processing → completed/failed).
    Usa conexión raw SQL para no depender de sesión ORM del hilo principal.
    """
    from app import db
    from app.services.gemini_service import run_deep_research_report, GeminiServiceError

    with app.app_context():
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
                        "UPDATE company_reports SET status = 'processing' WHERE id = :rid AND status = 'pending'"
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
        },
        daemon=True,
    )
    t.start()


def start_watchlist_batch_reports_thread(app, jobs):
    """
    Varios informes en un solo hilo, en serie (menos carga en API Gemini).

    jobs: lista de dicts con keys report_id, user_id, asset_id, description, points
    """
    import threading

    def worker():
        for job in jobs:
            run_company_report_deep_research_job(
                app,
                job['report_id'],
                job['user_id'],
                job['asset_id'],
                job['description'],
                job['points'],
                extra_prompt_suffix=WATCHLIST_MANUAL_FIELDS_PROMPT,
            )

    threading.Thread(target=worker, daemon=True).start()
