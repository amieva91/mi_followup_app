"""
Series diarias globales para el motor de estrategia global (^VIX, SPY, FEZ, 3188.HK).
El job `global-strategy-macro-daily-once` mantiene filas y sube `GlobalStrategyMacroState.data_version`.
"""
from datetime import datetime

from app import db


class GlobalStrategyMacroDaily(db.Model):
    __tablename__ = "global_strategy_macro_daily"

    series_key = db.Column(db.String(32), primary_key=True)
    yahoo_ticker = db.Column(db.String(64), nullable=False)
    data_points = db.Column(db.JSON, nullable=False, default=list)
    hist_end_date = db.Column(db.String(16), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GlobalStrategyMacroState(db.Model):
    """Singleton id=1: versión monotónica para invalidar lecturas; modo USA documentado."""

    __tablename__ = "global_strategy_macro_state"

    id = db.Column(db.Integer, primary_key=True)
    data_version = db.Column(db.Integer, nullable=False, default=0)
    usa_score_mode = db.Column(db.String(16), nullable=False, default="vix")
    updated_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def get_singleton() -> "GlobalStrategyMacroState":
        row = GlobalStrategyMacroState.query.get(1)
        if row:
            return row
        row = GlobalStrategyMacroState(id=1, data_version=0, usa_score_mode="vix", updated_at=datetime.utcnow())
        db.session.add(row)
        db.session.commit()
        return row
