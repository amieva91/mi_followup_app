"""
Snapshot de Euribor 12M (BCE). Columnas Yahoo/spread/tendencia heredadas; nuevas filas solo rellenan BCE.
Rellenado por cron vía `interest_rate_context_service.refresh_snapshot`.
"""
from datetime import datetime

from app import db


class InterestRateContextSnapshot(db.Model):
    __tablename__ = "interest_rate_context_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    bce_euribor_12m_percent = db.Column(db.Numeric(12, 6), nullable=True)
    bce_time_period = db.Column(db.String(16), nullable=True)

    yahoo_esr_f_price = db.Column(db.Numeric(14, 6), nullable=True)
    yahoo_implied_percent = db.Column(db.Numeric(12, 6), nullable=True)
    spread_implied_minus_bce = db.Column(db.Numeric(12, 6), nullable=True)

    trend_label = db.Column(db.String(32), nullable=False, default="desconocido")

    bce_fetch_error = db.Column(db.String(512), nullable=True)
    yahoo_fetch_error = db.Column(db.String(512), nullable=True)
