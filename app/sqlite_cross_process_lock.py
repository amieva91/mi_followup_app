"""
Serialización global de acceso a SQLite entre procesos (Flask + cron).

Solo flock en before_flush llega tarde: las SELECT abren transacción antes del flush
y el job de precios puede dejar la conexión ocupada durante la llamada HTTP a Yahoo.

Aquí: flock advisory sobre instance/followup.db.advisory.flock.
- Peticiones GET/HEAD/OPTIONS usan LOCK_SH: varias lecturas en paralelo entre workers.
- POST/PUT/PATCH/DELETE usan LOCK_EX: una mutación a la vez respecto al resto.
- El cron price-poll-one NO debe envolver la llamada HTTP a Yahoo con el lock global
  (bloqueaba todo el sitio cada minuto); SQLite WAL + busy_timeout gestionan el commit.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_registered = False

# Endpoints que solo leen estado en disco (JSON) o hacen lecturas ligeras y deben poder
# ejecutarse en paralelo al resto. Sin esto, un POST largo (p. ej. import CSV) mantiene
# flock(LOCK_EX) durante toda la petición y los GET de progreso quedan bloqueados: la UI
# se queda en 0% hasta el final (solo pasa en Linux/producción con fcntl).
_SKIP_FLOCK_ENDPOINTS = frozenset({
    'portfolio.import_progress',
    'portfolio.price_update_progress',
})


def _lock_path(app) -> str:
    return os.path.join(app.instance_path, 'followup.db.advisory.flock')


def _use_sqlite_file(app) -> bool:
    uri = (app.config.get('SQLALCHEMY_DATABASE_URI') or '').lower()
    return 'sqlite' in uri and ':memory:' not in uri


@contextmanager
def exclusive_db_lock(app):
    """Context manager para cron/CLI: mismo fichero que las peticiones Flask."""
    if not _use_sqlite_file(app):
        yield
        return
    try:
        import fcntl
    except ImportError:
        yield
        return

    os.makedirs(app.instance_path, exist_ok=True)
    path = _lock_path(app)
    fp = open(path, 'a+')
    fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            fp.close()
        except Exception:
            pass


def register_sqlite_cross_process_lock(app, db=None) -> None:
    """before_request: flock SH (lecturas) o EX (escrituras); teardown: liberar."""
    global _registered

    if not _use_sqlite_file(app) or app.config.get('TESTING'):
        return
    try:
        import fcntl
    except ImportError:
        logger.warning('fcntl no disponible: serialización SQLite desactivada')
        return

    if _registered:
        return
    _registered = True

    os.makedirs(app.instance_path, exist_ok=True)
    path = _lock_path(app)

    @app.before_request
    def _sqlite_request_lock_acquire():
        from flask import g, request

        if request.endpoint == 'static':
            return
        if request.path.startswith('/static/'):
            return
        if request.endpoint in _SKIP_FLOCK_ENDPOINTS:
            return
        fp = open(path, 'a+')
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            fcntl.flock(fp.fileno(), fcntl.LOCK_SH)
        else:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        g._sqlite_site_lock_fp = fp

    @app.teardown_request
    def _sqlite_request_lock_release(_exc):
        from flask import g

        fp = getattr(g, '_sqlite_site_lock_fp', None)
        if fp is None:
            return
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            fp.close()
        except Exception:
            pass
        g._sqlite_site_lock_fp = None
