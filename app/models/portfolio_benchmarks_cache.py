"""
Cache del estado "index-comparison" del portfolio (benchmarks vs portfolio).

Se usa un patrón HIST/NOW:
- HIST: datos que requieren reconstrucción completa cuando cambia el pasado.
- NOW: recalculo frecuente solo para el tramo actual cuando cambia "hoy".
"""

from datetime import datetime, timedelta

from flask import current_app

from app import db


class PortfolioBenchmarksCache(db.Model):
    __tablename__ = 'portfolio_benchmarks_cache'

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

