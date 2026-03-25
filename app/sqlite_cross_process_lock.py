"""
Serialización global de acceso a SQLite entre procesos (Flask + cron).

Solo flock en before_flush llega tarde: las SELECT abren transacción antes del flush
y el job de precios puede dejar la conexión ocupada durante la llamada HTTP a Yahoo.

Aquí: un único flock (instance/followup.db.advisory.flock) durante toda la petición HTTP
y durante todo el comando CLI que toca la BD.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_registered = False


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
    """before_request: flock EX; teardown_request: liberar. Solo SQLite en disco."""
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
        fp = open(path, 'a+')
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
