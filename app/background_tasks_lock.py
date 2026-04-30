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
import threading

logger = logging.getLogger(__name__)

_THREAD_LOCK = threading.Lock()


def _lock_path(app) -> str:
    return os.path.join(app.instance_path, "followup.background_tasks.lock")


@contextmanager
def background_tasks_lock(app):
    """
    Lock exclusivo para ejecuciones largas.

    - Cross-process: funciona con varios workers gunicorn.
    - Bloqueante: el que llegue después espera sin consumir CPU.
    """
    # 1) Lock intra-proceso (threads): fcntl.flock no bloquea entre threads del mismo proceso.
    _THREAD_LOCK.acquire()
    fp = None
    try:
        # 2) Lock cross-proceso (gunicorn multi-worker)
        try:
            import fcntl  # type: ignore
        except ImportError:
            yield
            return

        os.makedirs(app.instance_path, exist_ok=True)
        path = _lock_path(app)
        fp = open(path, "a+")
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            try:
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
    finally:
        try:
            if fp is not None:
                fp.close()
        except Exception:
            pass
        _THREAD_LOCK.release()

