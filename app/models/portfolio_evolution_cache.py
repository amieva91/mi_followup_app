"""
Cache del estado "performance" del portfolio (evolución para gráficos).

Se usa un patrón HIST/NOW:
- HIST: serie histórica de fechas hasta el último rebuild completo.
- NOW: recálculo frecuente solo del tramo actual (último punto) cuando hay cambios de "hoy".
"""

from datetime import datetime, timedelta

from flask import current_app

from app import db


class PortfolioEvolutionCache(db.Model):
    __tablename__ = 'portfolio_evolution_cache'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)

    cached_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    @property
    def is_valid(self) -> bool:
        return self.expires_at > datetime.utcnow()

    @staticmethod
    def get_default_expiry() -> datetime:
        # Reutilizamos el mismo TTL del dashboard por defecto.
        minutes = current_app.config.get('DASHBOARD_CACHE_MINUTES', 15)
        return datetime.utcnow() + timedelta(minutes=minutes)

