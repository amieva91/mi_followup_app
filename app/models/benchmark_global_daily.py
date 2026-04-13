"""
Serie diaria global por benchmark (misma para todos los usuarios).
El job `benchmark-global-daily-once` mantiene filas y sube `BenchmarkGlobalState.daily_data_version`.
"""
from datetime import datetime

from app import db


class BenchmarkGlobalDaily(db.Model):
    __tablename__ = "benchmark_global_daily"

    benchmark_name = db.Column(db.String(128), primary_key=True)
    yahoo_ticker = db.Column(db.String(64), nullable=False)
    data_points = db.Column(db.JSON, nullable=False, default=list)
    hist_end_date = db.Column(db.String(16), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BenchmarkGlobalState(db.Model):
    """Fila singleton (id=1): versión monotónica para invalidar lecturas en cachés por usuario."""

    __tablename__ = "benchmark_global_state"

    id = db.Column(db.Integer, primary_key=True)
    daily_data_version = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def get_singleton() -> "BenchmarkGlobalState":
        row = BenchmarkGlobalState.query.get(1)
        if row:
            return row
        row = BenchmarkGlobalState(id=1, daily_data_version=0, updated_at=datetime.utcnow())
        db.session.add(row)
        db.session.commit()
        return row
