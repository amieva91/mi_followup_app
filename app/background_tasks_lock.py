"""
Serialización global (cross-process) de tareas largas: Deep Research, TTS, correo, etc.

Objetivo: si el usuario lanza varias acciones (informes, todo-en-uno, audios) a la vez,
se ejecutan estrictamente **de una en una**, quedando el resto en espera.

No usamos el mismo flock que la BD (sqlite_cross_process_lock) para no bloquear lecturas GET del sitio.
Este lock es independiente y solo lo adquieren los hilos de background.
"""
from __future__ import annotations

import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def _lock_path(app) -> str:
    return os.path.join(app.instance_path, "followup.background_tasks.lock")


@contextmanager
def background_tasks_lock(app):
    """
    Lock exclusivo para ejecuciones largas.

    - Cross-process: funciona con varios workers gunicorn.
    - Bloqueante: el que llegue después espera sin consumir CPU.
    """
    try:
        import fcntl  # type: ignore
    except ImportError:
        # En plataformas sin fcntl, no podemos garantizar serialización global.
        yield
        return

    os.makedirs(app.instance_path, exist_ok=True)
    path = _lock_path(app)
    fp = open(path, "a+")
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
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

