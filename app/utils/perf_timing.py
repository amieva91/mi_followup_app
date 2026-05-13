"""
Marcas de rendimiento para logs (prefijo [perf]).

Uso:
    tick = new_tick()
    perf_mark("GET /dashboard", user_id, tick, "summary_cache_get")
"""
from __future__ import annotations

import logging
import time
from typing import Any, List, MutableSequence, Optional

logger = logging.getLogger("followup.perf")


def new_tick() -> List[float]:
    t = time.perf_counter()
    return [t, t]


def perf_mark(
    route: str,
    user_id: Optional[int],
    tick: MutableSequence[float],
    step: str,
    **kwargs: Any,
) -> None:
    now = time.perf_counter()
    step_ms = (now - tick[1]) * 1000
    total_ms = (now - tick[0]) * 1000
    extra = " ".join(f"{k}={v!s}" for k, v in kwargs.items())
    logger.info(
        "[perf] route=%s user_id=%s step=%s step_ms=%.1f total_ms=%.1f %s",
        route,
        user_id,
        step,
        step_ms,
        total_ms,
        extra,
    )
    tick[1] = now
