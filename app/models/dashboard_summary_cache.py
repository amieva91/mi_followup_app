"""
Cache del resumen del dashboard principal (patrimonio, histórico, widgets).
TTL corto (15 min) para que los datos no se queden obsoletos.
"""
from datetime import datetime, timedelta
from app import db


class DashboardSummaryCache(db.Model):
    __tablename__ = 'dashboard_summary_cache'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    cached_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    @property
    def is_valid(self):
        return self.expires_at > datetime.utcnow()

    @staticmethod
    def get_default_expiry():
        return datetime.utcnow() + timedelta(minutes=15)
