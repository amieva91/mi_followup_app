"""
Invalidación unificada de cachés tras mutaciones de datos de usuario.

Usar desde rutas de escritura (import, transacciones, CRUD de cartera, etc.)
en lugar de llamar servicios de caché por separado.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Sequence


def invalidate_user_data_caches(
    user_id: int,
    *,
    dates: Sequence[date | datetime] | None = None,
    month_refs: Iterable[tuple[int, int]] | None = None,
    full_history: bool = False,
    now: bool = False,
    metrics: bool = True,
    dashboard: bool = True,
    evolution_dates: Sequence[date | datetime] | None = None,
) -> None:
    """
    Invalida cachés y marca rebuild según el tipo de cambio.

    - ``full_history=True``: import masivo o cambio histórico → ``mark_full_history``.
    - ``now=True``: solo datos actuales → ``mark_now`` (si no hay FULL pendiente).
    - ``dates`` / ``month_refs``: delega en ``CacheRebuildStateService.mark_for_dates``.
    - ``metrics`` / ``dashboard``: invalida filas en ``MetricsCache`` / ``DashboardSummaryCache``.
    - ``evolution_dates``: ``PortfolioEvolutionCacheService.touch_for_dates`` (opcional).
    """
    from app.services.cache_rebuild_state_service import CacheRebuildStateService

    if full_history:
        CacheRebuildStateService.mark_full_history(user_id)
    elif now:
        CacheRebuildStateService.mark_now(user_id)
    elif dates or month_refs:
        CacheRebuildStateService.mark_for_dates(
            user_id,
            dates=list(dates) if dates else None,
            month_refs=list(month_refs) if month_refs else None,
        )

    if metrics:
        from app.services.metrics.cache import MetricsCacheService

        MetricsCacheService.invalidate(user_id)

    if dashboard:
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService

        DashboardSummaryCacheService.invalidate(user_id)

    if evolution_dates:
        from app.services.portfolio_evolution_cache import PortfolioEvolutionCacheService

        unique: list[date] = []
        seen: set[date] = set()
        for raw in evolution_dates:
            d = raw.date() if isinstance(raw, datetime) else raw
            if isinstance(d, date) and d not in seen:
                seen.add(d)
                unique.append(d)
        if unique:
            PortfolioEvolutionCacheService.touch_for_dates(user_id, unique)
