"""
Serialización global (cross-process) de tareas largas: Deep Research, TTS, correo, etc.

Con ``fair_report_id``, solo entra en la sección crítica el informe que encabeza la cola
global (misma orden que ``sorted_active_queue_rows`` en ``company_report_queue``), aunque
``fcntl.flock`` despierte a otro waiter primero.
"""
from __future__ import annotations

import os
import logging
import time
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

_THREAD_LOCK = threading.Lock()

# Reintento cuando no es nuestro turno; el flock ya no garantiza FIFO entre waiters.
_FAIR_RETRY_SLEEP_SEC = 0.35
# Evitar bloqueo eterno si el cabeza de cola no tiene hilo vivo.
_MAX_FAIR_WAIT_SEC = 86400


def _lock_path(app) -> str:
    return os.path.join(app.instance_path, "followup.background_tasks.lock")


@contextmanager
def background_tasks_lock(app, fair_report_id: int | None = None):
    """
    Lock exclusivo para ejecuciones largas.

    - Cross-process: funciona con varios workers gunicorn.
    - Bloqueante: el que llegue después espera sin consumir CPU.
    - ``fair_report_id``: esperar activamente hasta ser cabeza de cola global (o timeout).
    """
    _THREAD_LOCK.acquire()
    fp = None
    try:
        try:
            import fcntl  # type: ignore
        except ImportError:
            yield
            return

        os.makedirs(app.instance_path, exist_ok=True)
        path = _lock_path(app)
        deadline = time.monotonic() + _MAX_FAIR_WAIT_SEC if fair_report_id is not None else None
        head: int | None = None

        while True:
            fp = open(path, "a+")
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
            if fair_report_id is None:
                break

            from app.services.company_report_queue import (
                first_in_global_report_queue,
                report_id_in_active_global_queue,
            )

            rid = int(fair_report_id)
            if not report_id_in_active_global_queue(rid):
                break

            head = first_in_global_report_queue()
            if head is None or int(head) == rid:
                break

            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            fp.close()
            fp = None

            if deadline is not None and time.monotonic() >= deadline:
                logger.warning(
                    "background_tasks_lock: fair wait timeout report_id=%s queue_head=%s",
                    rid,
                    head,
                )
                fp = open(path, "a+")
                fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
                break

            time.sleep(_FAIR_RETRY_SLEEP_SEC)

        try:
            yield
        finally:
            if fp is not None:
                try:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    fp.close()
                except Exception:
                    pass
    finally:
        _THREAD_LOCK.release()
