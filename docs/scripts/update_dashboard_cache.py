"""
Actualizar el cache del dashboard (/dashboard) para uno o varios usuarios.

Uso (en desarrollo o producción, siempre con FLASK_APP configurado):

    FLASK_APP=run.py python docs/scripts/update_dashboard_cache.py

Opciones:
    - Sin argumentos: recorre todos los usuarios activos y asegura que
      tengan un snapshot de dashboard en cache, recalculando solo la parte
      "actual" cuando ya exista histórico cacheado.

    - Con argumento de usuario:
        FLASK_APP=run.py python docs/scripts/update_dashboard_cache.py amieva91
      o un id numérico:
        FLASK_APP=run.py python docs/scripts/update_dashboard_cache.py 1
"""

import sys
from typing import Optional

from app import create_app, db
from app.models import User, DashboardSummaryCache
from app.services.net_worth_service import get_dashboard_summary
from app.services.dashboard_summary_cache import DashboardSummaryCacheService


def _find_user(identifier: str) -> Optional[User]:
    """Busca usuario por id numérico o username/email."""
    if identifier.isdigit():
        return User.query.get(int(identifier))
    return (
        User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        )
        .order_by(User.id)
        .first()
    )


def update_dashboard_cache_for_user(user: User) -> None:
    """Actualiza el cache de dashboard para un usuario concreto."""
    print(f"▶ Usuario {user.id} ({user.username})")
    cache = DashboardSummaryCache.query.filter_by(user_id=user.id).first()

    if cache is None:
        print("   - Sin cache previo: calculando snapshot completo…")
        summary = get_dashboard_summary(user.id)
        DashboardSummaryCacheService.set(user.id, summary)
        print("   ✓ Snapshot creado")
        return

    data = cache.cached_data or {}
    has_history_block = bool(data.get("history_block") or data.get("history"))
    has_breakdown = "breakdown" in data

    if has_history_block and has_breakdown:
        print("   - Reutilizando histórico cacheado; recalculando solo estado actual…")
        updated = DashboardSummaryCacheService.recompute_current_from_cache(user.id)
        if updated is None:
            print("   ⚠ No se pudo recalcular solo current; recalculando snapshot completo…")
            summary = get_dashboard_summary(user.id)
            DashboardSummaryCacheService.set(user.id, summary)
        else:
            print("   ✓ Estado actual actualizado a partir del histórico cacheado")
    else:
        print("   - Cache incompleto (sin histórico o breakdown); recalculando snapshot completo…")
        summary = get_dashboard_summary(user.id)
        DashboardSummaryCacheService.set(user.id, summary)
        print("   ✓ Snapshot completo actualizado")


def run(target_identifier: Optional[str] = None) -> None:
    """Punto de entrada principal del script."""
    # Crear app con la configuración indicada por FLASK_ENV
    # (en desarrollo normalmente 'development', en producción 'production')
    app = create_app()

    with app.app_context():
        if target_identifier:
            user = _find_user(target_identifier)
            if not user:
                print(f"❌ No se encontró usuario para '{target_identifier}'")
                return
            update_dashboard_cache_for_user(user)
            return

        # Sin filtro: recorrer todos los usuarios activos
        users = User.query.filter_by(is_active=True).order_by(User.id).all()
        print(f"🔁 Actualizando cache de dashboard para {len(users)} usuarios activos…")
        for u in users:
            try:
                update_dashboard_cache_for_user(u)
                # Evitar que errores de un usuario rompan todo el script
                db.session.remove()
            except Exception as e:  # pragma: no cover (script de mantenimiento)
                db.session.rollback()
                print(f"   ⚠ Error actualizando usuario {u.id} ({u.username}): {e}")


if __name__ == "__main__":
    identifier = sys.argv[1] if len(sys.argv) > 1 else None
    run(identifier)

