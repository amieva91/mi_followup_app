"""
Estado del job de polling de precios (índice actual, última ejecución).
"""
from datetime import datetime
from app import db


class PricePollingState(db.Model):
    """Estado global del job de polling (1 fila por instancia)."""
    __tablename__ = 'price_polling_state'

    id = db.Column(db.Integer, primary_key=True)
    last_asset_index = db.Column(db.Integer, default=0, nullable=False)
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_updated_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
