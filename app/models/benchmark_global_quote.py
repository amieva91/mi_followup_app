"""
Cotización global (NOW) por benchmark/índice, actualizada por el job price-poll-one.
Misma serie de precios para todos los usuarios; no es un Asset.
"""
from datetime import datetime

from app import db


class BenchmarkGlobalQuote(db.Model):
    __tablename__ = "benchmark_global_quote"

    benchmark_name = db.Column(db.String(128), primary_key=True)
    yahoo_ticker = db.Column(db.String(64), nullable=False)
    regular_market_price = db.Column(db.Float, nullable=True)
    previous_close = db.Column(db.Float, nullable=True)
    day_change_percent = db.Column(db.Float, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
