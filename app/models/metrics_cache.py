"""
Modelo para cachear métricas calculadas del portfolio
"""
from datetime import datetime, timedelta
from app import db


class MetricsCache(db.Model):
    """
    Cache de métricas del portfolio para evitar recálculos costosos.
    
    Las métricas se guardan en formato JSON y expiran después de 24 horas.
    El cache se invalida automáticamente cuando:
    - Se crea/edita/elimina una transacción
    - Se actualizan precios
    - Se actualiza conversión de divisas
    """
    __tablename__ = 'metrics_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Datos cacheados en formato JSON
    cached_data = db.Column(db.JSON, nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    # Relación con User
    user = db.relationship('User', backref=db.backref('metrics_cache', uselist=False))
    
    def __repr__(self):
        return f'<MetricsCache user_id={self.user_id} expires_at={self.expires_at}>'
    
    @property
    def is_valid(self):
        """Verifica si el cache aún es válido (no expiró)"""
        return self.expires_at > datetime.utcnow()
    
    @property
    def time_until_expiry(self):
        """Retorna el tiempo restante hasta la expiración"""
        if not self.is_valid:
            return timedelta(0)
        return self.expires_at - datetime.utcnow()
    
    @staticmethod
    def get_default_expiry():
        """Retorna la fecha de expiración por defecto (24 horas desde ahora)"""
        return datetime.utcnow() + timedelta(hours=24)

