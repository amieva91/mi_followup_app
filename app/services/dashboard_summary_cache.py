"""
Cache del resumen del dashboard principal (/dashboard).
TTL 15 min; se invalida al cambiar transacciones, gastos, ingresos, bancos, inmuebles, deudas.
"""
from datetime import date, datetime
from app import db
from app.models.dashboard_summary_cache import DashboardSummaryCache


def _make_json_serializable(obj):
    """Convierte recursivamente date/datetime a string ISO para que el JSON sea serializable."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_serializable(v) for v in obj]
    return obj


class DashboardSummaryCacheService:
    @staticmethod
    def get(user_id: int):
        cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
        if not cache or not cache.is_valid:
            if cache:
                db.session.delete(cache)
                db.session.commit()
            return None
        data = cache.cached_data.copy()
        data['_from_cache'] = True
        data['_cached_at'] = cache.created_at.isoformat()
        return data

    @staticmethod
    def set(user_id: int, data: dict):
        clean = {k: v for k, v in data.items() if not str(k).startswith('_')}
        clean = _make_json_serializable(clean)
        cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
        if cache:
            cache.cached_data = clean
            cache.created_at = datetime.utcnow()
            cache.expires_at = DashboardSummaryCache.get_default_expiry()
        else:
            cache = DashboardSummaryCache(
                user_id=user_id,
                cached_data=clean,
                created_at=datetime.utcnow(),
                expires_at=DashboardSummaryCache.get_default_expiry(),
            )
            db.session.add(cache)
        db.session.commit()
        return cache

    @staticmethod
    def invalidate(user_id: int) -> bool:
        cache = DashboardSummaryCache.query.filter_by(user_id=user_id).first()
        if cache:
            db.session.delete(cache)
            db.session.commit()
            return True
        return False
